sudo apt -y install rpd-plym-splash feh
sudo raspi-config nonint do_boot_behaviour 4
sudo cp ./vanity/splash.png /usr/share/plymouth/themes/pix/splash.png
sudo raspi-config nonint do_boot_splash 0
sudo sh -c 'echo "disable_splash=1\n" >> /boot/config.txt'
