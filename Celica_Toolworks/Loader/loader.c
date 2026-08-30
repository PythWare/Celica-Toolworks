#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PACKAGEMGR_VTABLE_RVA 0x00b16ce8
#define FILEDEVICE_VTABLE_RVA 0x00af69b0
#define STAT_SLOT             6
#define STAT_FUNC_RVA         0x0088e540
#define DEVICE_STAT_RVA       0x00813230
#define STAT_FUNC_SIGNATURE   0x5540
#define LOG_LIMIT             200

typedef char (*stat_fn)(void *self, const char *path, void *info);

static stat_fn original_stat = NULL;
static stat_fn original_device_stat = NULL;
static void **vtable_slot = NULL;
static void **device_slot = NULL;
static unsigned char *module_base = NULL;
static char game_root[MAX_PATH];
static char log_path[MAX_PATH];
static char verbose_path[MAX_PATH];
static CRITICAL_SECTION log_lock;
static int verbose = 0;
static unsigned long long seen_count = 0;
static unsigned long long override_count = 0;
static unsigned long long logged_count = 0;

static void write_log(const char *format, ...)
{
    va_list args;
    FILE *handle;

    EnterCriticalSection(&log_lock);
    handle = fopen(log_path, "a");
    if (handle)
    {
        va_start(args, format);
        vfprintf(handle, format, args);
        va_end(args);
        fputc('\n', handle);
        fclose(handle);
    }
    LeaveCriticalSection(&log_lock);
}

static int ends_with(const char *text, const char *suffix)
{
    size_t a = strlen(text);
    size_t b = strlen(suffix);

    if (b > a)
        return 0;
    return _stricmp(text + a - b, suffix) == 0;
}

static int loose_path_for(const char *path, char *out, size_t out_size)
{
    DWORD attributes;
    size_t i;

    if (_snprintf(out, out_size, "%s\\%s", game_root, path) < 0)
        return 0;
    out[out_size - 1] = 0;

    for (i = 0; out[i]; i++)
    {
        if (out[i] == '/')
            out[i] = '\\';
    }

    attributes = GetFileAttributesA(out);
    if (attributes == INVALID_FILE_ATTRIBUTES)
        return 0;
    if (attributes & FILE_ATTRIBUTE_DIRECTORY)
        return 0;
    return 1;
}

static int should_override(const char *path, char *out, size_t out_size)
{
    if (!path || !path[0])
        return 0;
    if (path[0] == '/' || path[0] == '\\')
        return 0;
    if (strchr(path, ':'))
        return 0;
    if (ends_with(path, ".apk") || ends_with(path, "pack.idx"))
        return 0;

    return loose_path_for(path, out, out_size);
}

static char device_stat_hook(void *self, const char *path, void *info)
{
    char result = original_device_stat(self, path, info);

    if (verbose && path && path[0])
        write_log("DISK found=%d %s", (int)result, path);

    return result;
}

static char stat_hook(void *self, const char *path, void *info)
{
    char resolved[MAX_PATH * 2];
    char result;

    if (should_override(path, resolved, sizeof(resolved)))
    {
        override_count++;
        if (logged_count < LOG_LIMIT)
        {
            logged_count++;
            write_log("LOOSE %s", path);
        }
        return 0;
    }

    result = original_stat(self, path, info);

    if (path && path[0])
    {
        seen_count++;
        if (verbose)
            write_log("PACK found=%d %s", (int)result, path);
    }

    return result;
}

static int code_is_ready(unsigned char *base)
{
    unsigned short signature;

    if (IsBadReadPtr(base + STAT_FUNC_RVA, 2))
        return 0;

    memcpy(&signature, base + STAT_FUNC_RVA, 2);
    return signature == STAT_FUNC_SIGNATURE;
}

static int swap_slot(unsigned char *base, unsigned long vtable_rva,
                     unsigned long expected_rva, void *replacement,
                     stat_fn *saved, void ***slot_out)
{
    DWORD previous;
    void **slot;

    slot = (void **)(base + vtable_rva + STAT_SLOT * sizeof(void *));

    if (IsBadReadPtr(slot, sizeof(void *)))
        return 0;

    if (*slot != (void *)(base + expected_rva))
    {
        write_log("slot %#lx holds %p, expected %p",
                  vtable_rva, *slot, (void *)(base + expected_rva));
        return 0;
    }

    if (!VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &previous))
        return 0;

    *saved = (stat_fn)*slot;
    *slot = replacement;
    *slot_out = slot;

    VirtualProtect(slot, sizeof(void *), previous, &previous);
    return 1;
}

static void restore_slot(void **slot, stat_fn saved)
{
    DWORD previous;

    if (!slot || !saved)
        return;

    if (VirtualProtect(slot, sizeof(void *), PAGE_READWRITE, &previous))
    {
        *slot = (void *)saved;
        VirtualProtect(slot, sizeof(void *), previous, &previous);
    }
}

static DWORD WINAPI loader_thread(LPVOID unused)
{
    int attempts;

    (void)unused;

    write_log("loader online, base %p", module_base);
    write_log("loose root %s", game_root);
    write_log("verbose %d", verbose);

    for (attempts = 0; attempts < 6000; attempts++)
    {
        if (code_is_ready(module_base))
            break;
        Sleep(50);
    }

    if (!code_is_ready(module_base))
    {
        write_log("timed out waiting for code section to decrypt");
        return 0;
    }

    write_log("code ready after %d poll(s)", attempts);

    if (swap_slot(module_base, PACKAGEMGR_VTABLE_RVA, STAT_FUNC_RVA,
                  (void *)stat_hook, &original_stat, &vtable_slot))
        write_log("pack hook installed");
    else
        write_log("pack hook failed");

    if (verbose)
    {
        if (swap_slot(module_base, FILEDEVICE_VTABLE_RVA, DEVICE_STAT_RVA,
                      (void *)device_stat_hook, &original_device_stat, &device_slot))
            write_log("disk hook installed");
        else
            write_log("disk hook failed");
    }

    return 0;
}

static void build_paths(void)
{
    char module_path[MAX_PATH];
    char *cursor;

    GetModuleFileNameA(NULL, module_path, MAX_PATH);
    cursor = strrchr(module_path, '\\');
    if (cursor)
        *cursor = 0;

    strcpy(game_root, module_path);

    _snprintf(log_path, MAX_PATH, "%s\\sao_loader.log", module_path);
    log_path[MAX_PATH - 1] = 0;

    _snprintf(verbose_path, MAX_PATH, "%s\\sao_loader_verbose.txt", module_path);
    verbose_path[MAX_PATH - 1] = 0;

    verbose = GetFileAttributesA(verbose_path) != INVALID_FILE_ATTRIBUTES;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved)
{
    HANDLE thread;

    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH)
    {
        DisableThreadLibraryCalls(instance);
        InitializeCriticalSection(&log_lock);
        build_paths();

        module_base = (unsigned char *)GetModuleHandleA(NULL);

        DeleteFileA(log_path);

        thread = CreateThread(NULL, 0, loader_thread, NULL, 0, NULL);
        if (thread)
            CloseHandle(thread);
    }
    else if (reason == DLL_PROCESS_DETACH)
    {
        restore_slot(vtable_slot, original_stat);
        restore_slot(device_slot, original_device_stat);
        write_log("loader offline, %llu packed lookups, %llu loose overrides",
                  seen_count, override_count);
        DeleteCriticalSection(&log_lock);
    }

    return TRUE;
}
