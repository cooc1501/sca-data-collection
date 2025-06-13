# Dataset Collection Suite
A script to simplify the collection of SCA datasets with the chipwhisperer nano. Utilizes a patched version of the chipwhisperer simple serial AES implementation to increase data collection rate.

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
In order to accurately quantify and compare the leakage between devices, a larger dataset is required for a subset of the devices. This is because modern leakage quantification techniques such as TVLA or NICV typically require more traces than would be necessary to conduct an effective attack on the same device. A dataset of 50,000 random traces for a subset of 5 of the devices, as well as a 50,000 trace TVLA dataset for a subset of 3 of the devices should be sufficient for accurate leakage quantification and comparison. It doesn't matter which of the devices are used, so long as their device ID is recorded so that they can be accurately linked to the previous dataset.

Example usage:
```
python collect.py -d 2 -t random  # collect 50000 random traces, export dataset
python collect.py -d 4 -t tvla  # collect 50000 tvla traces, export dataset
```

`-d`: **required** device id as an integer</br>
`-t`: **required** dataset type as a stiring, one of [tvla, random]</br>
`-n`: number of traces to record (default: 50000)</br>
`--delay`: delay between successive encryptions in (target) clock ticks. The default value of 10000 should work, but if you see `"Timeout in OpenADC capture()"` errors **after** the warmup stage this value should be increased</br>

After the traces have been collected, they will be automatically be exported to the root directory of this repo by the name `Device <dev_id> <n_traces> <dataset_type> Traces`. 
