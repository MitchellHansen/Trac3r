sudo apt-get install python3-pil python3-pil.imagetk
sudo apt install libcairo2-dev pkg-config
virtualenv -p python3 .env 
source .env/bin/activate
pip3 install -r requirements.txt
