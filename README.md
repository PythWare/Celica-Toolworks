# Celica Toolworks

Inspired by Yang Xiao Long from RWBY, Celica Toolworks is a toolkit that makes Sword Art Online Lost Song easily moddable. Includes a custom SAO inspired GUI I designed.

Scroll down for example images of the GUI if desired

# Requirements

Python installed, that's pretty much it. It's a lightweight but rad toolkit.

# How to run

double click main.pyw, should run after that. If it has issues with double clicking then open cmd in the current directory and type python main.pyw

If Celica Toolworks doesnt launch it's usually caused by Python not being installed correctly or .pyw file associations using the wrong Python. Please verify your Python installation before reporting a bug.

# Controls

The GUI is intentionally designed to be unique, it doesn't look like a standard GUI app.

To move the app around you must use right click on the GUI.

To exit, click the esc button on your keyboard.

Press F1 to toggle on/off always on top mode.

# T spherical button

T is for tools. Set Path button tells Celica Toolworks where your lost song game directory is, Unpack button will unpack the game to the game's directory (should be super quick, only takes 5 seconds for me), Patch DLL button will backup the game's d3dcompiler_47.dll file and place the one I created in the game's directory (this allows the game to load loose files without having to patch the executable), Revert DLL will disable loose file loading and return your original d3dcompiler_47.dll to the game.

# Modding workflow

Since Celica Toolworks can force Lost Song to read loose files, there's no need for a mod manager or rebuilding of the apk containers the game has. The workflow is extremely easy especially because all unpacked files retain their original filenames.

Modders will mod whatever unpacked files they want, then start the game. The game will simply read the unpacked files as long as you used the Patch DLL button

Gamers who only intend to download mods just need to Unpack the game with the Unpack button and extract the downloaded mods (nexus or wherever) you have to Sword Art Online Lost Song\data folder. After that, just start the game.

# About adding new assets to Lost Song

Entirely possible to do, you'd just need to reference new files. For example, subquests/missions are referenced in the unpacked files along with a list of all available quests. So if you intended to make a custom quest mod (super easy to do, lua/csv are used heavily for the quests) as an example, depending on the complexity of the quest you'd either just make a new .lua file or create additional lua/csv/etc files and update the file that references all quests. That's just a basic example, the game will load new assets without needing to replace if you identify the unpacked file that stores references of what files to load.

Interestingly, Lost Song has over 60 cut/unused quests. There are quite a bit of unused quests that are complete enough to enable for the game.

# GUI examples

Celica Toolworks has a transparent background, meant to match the SAO UI theme but with Yang Xiao Long inspired coloring.

<img width="919" height="497" alt="4" src="https://github.com/user-attachments/assets/2a30be07-2cb2-4014-9c80-c10e17d3ad1c" />

<img width="876" height="513" alt="5" src="https://github.com/user-attachments/assets/29c08252-988d-4064-9089-922101c082dd" />

<img width="1037" height="747" alt="6" src="https://github.com/user-attachments/assets/e6265c1c-1972-49e2-93df-126ef31364d1" />

<img width="1914" height="1031" alt="4" src="https://github.com/user-attachments/assets/e41092f0-e773-47e7-9f3d-8be5210351dc" />

# Examples of models rendered

<img width="1072" height="652" alt="7" src="https://github.com/user-attachments/assets/015f8c90-4d24-4086-9cc5-30f8006e11a7" />

<img width="1361" height="801" alt="8" src="https://github.com/user-attachments/assets/b8ed3dca-68e9-4809-a57c-67ec3240ae26" />

<img width="1100" height="788" alt="9" src="https://github.com/user-attachments/assets/e5486fda-1533-4d2a-86fd-f00953e970ac" />

<img width="1478" height="781" alt="10" src="https://github.com/user-attachments/assets/09505400-4c3d-44c2-b1a6-10586edf89f7" />

<img width="1332" height="775" alt="12" src="https://github.com/user-attachments/assets/cad5aa9a-8f4c-4cde-8cab-f8bb52a75bc0" />

# Examples of the vanilla game and an example mod applied

<img width="1269" height="951" alt="6" src="https://github.com/user-attachments/assets/18e2ae8e-b472-49f1-94b1-14ab5c28d1cb" />

<img width="1266" height="959" alt="5" src="https://github.com/user-attachments/assets/b433ba07-601b-4e8f-8f1e-43dd323e006e" />

# Examples of unused/cut quests

Since there are over 60 unused quests i'm only showing some of them on here so the repository isn't bloated with images. 

The lisbeth one (指輪を求めて（１）リズベット) according to google translate is:

In Search of the Ring (1) Lisbeth

Silica one (黄金のリンゴ（１）シリカ) is:

The Golden Apple (1)  Silica

No idea how accurate those translations are, it's just what google translate says. The third image is a discarded quest

<img width="475" height="440" alt="18" src="https://github.com/user-attachments/assets/2d83f72f-ebc4-4e50-9640-57b3a15f3447" />

<img width="473" height="417" alt="19" src="https://github.com/user-attachments/assets/f852c71d-3996-4a4e-93f7-66e787e12a0b" />

<img width="470" height="52" alt="20" src="https://github.com/user-attachments/assets/8363ab44-6333-4eb4-a4ac-2f697e30464c" />
