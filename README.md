Visual discrimination code for tracking mice in the McNaughton lab.

### INSTALLATION ###

Download the github code repository as a zip:

<img width="255" height="216" alt="image" src="https://github.com/user-attachments/assets/0533f590-2cb4-410c-a1e9-f34e12ec79aa" />

Then unzip it, open powershell and change to the unzipped directory:

`cd C:\Users\rbain\Downloads\viz-main`

Run the first powershell installation script:

`powershell -ExecutionPolicy Bypass -File .\install_1.ps1`

Follow the instructions on screen. This will ask you to restart powershell in admin mode. Then run the final installation script:

`powershell -ExecutionPolicy Bypass -File .\install_2.ps1`

### HOW TO USE ###

Open powershell and enter:

`conda activate viz`

Change to the directory where you've installed this repository:

`cd C:\Users\rbain\Downloads\viz-main`

Final step: Start the flask server.

`python server.py`
