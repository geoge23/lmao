#!/bin/bash
source ~/app/evars.sh
cd ~/app/client
export DISPLAY=:0
#sets the background to the desktop.png file in the vanity folder
feh --bg-scale ../vanity/desktop.png
until python main.py; do
    #Code 143 is a SIGTERM, meaning the operating system (or a program) killed LMAO.
    #This act is almost certainly intentional, so the daemon will die when this happens
    if [ $? -eq 143 ]; then
        echo "LMAO was killed, closing" >&1
        break
    else
        source ~/app/evars.sh
        echo "LMAO crashed with exit code $?.  Respawning.." >&2
    fi
done
