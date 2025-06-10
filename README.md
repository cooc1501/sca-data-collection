# Dataset Collection Suite
A script to simplify the collection of SCA datasets with the chipwhisperer nano. Utilizes a patched versoin of the chipwhisperer simple serial AES implementation to increase data collection rate.

## Installation
Clone this repository and initialize submodules
```
git clone https://github.com/cooc1501/sca-data-collection.git
git submodule update --init
```

Create a python virutal environment
```
python -m venv ./.venv && . .venv/bin/activate
```

Install Dependencies
```
pip install -r requirements.txt
```

## Usage
