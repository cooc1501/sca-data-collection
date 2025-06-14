import os
from argparse import ArgumentParser
import subprocess

import chipwhisperer as cw
import numpy as np
from tqdm import tqdm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from dataset import Dataset

# We don't have a CW-Nano to test on, any connection errors likely originate here
def connect_nano(aes_delay: int = 1e4) -> tuple[cw.scope, cw.target]:
    SCOPETYPE = 'CWNANO'
    PLATFORM = 'CWNANO'
    CRYPTO_TARGET = 'TINYAES128C'
    SS_VER = 'SS_VER_2_1'

    try:
        if not scope.connectStatus:
            scope.con()
    except NameError:
        scope = cw.scope()

    target_type = cw.targets.SimpleSerial2
    target = cw.target(scope, target_type)
    prog = cw.programmers.STM32FProgrammer

    scope.default_setup()

    # Build and Flash firmware
    firmware_dir = os.path.join(os.path.dirname(__file__), 'chipwhisperer/firmware/mcu/simpleserial-aes-batch')
    ret = subprocess.run(["make", f"EXTRA_OPTS=DELAY={aes_delay}", f"PLATFORM={PLATFORM}", f"CRYPTO_TARGET={CRYPTO_TARGET}", f"SS_VER={SS_VER}"], cwd=firmware_dir)
    cw.program_target(scope, prog, os.path.join(firmware_dir, "simpleserial-aes-batch-CWNANO.hex"))
    
    return scope, target

def _connect_husky(aes_delay: int = 1e4) -> tuple[cw.scope, cw.target]:
    SCOPETYPE = 'OPENADC'
    PLATFORM = 'CWHUSKY'
    CRYPTO_TARGET = 'TINYAES128C'
    SS_VER = 'SS_VER_2_1'

    try:
        if not scope.connectStatus:
            scope.con()
    except NameError:
        scope = cw.scope()

    target_type = cw.targets.SimpleSerial2
    target = cw.target(scope, target_type)
    prog = cw.programmers.SAM4SProgrammer

    scope.default_setup()

    # Build and Flash firmware
    firmware_dir = os.path.join(os.path.dirname(__file__), 'chipwhisperer/firmware/mcu/simpleserial-aes-batch')
    ret = subprocess.run(["make", f"EXTRA_OPTS=DELAY={aes_delay}", f"PLATFORM={PLATFORM}", f"CRYPTO_TARGET={CRYPTO_TARGET}", f"SS_VER={SS_VER}"], cwd=firmware_dir)
    cw.program_target(scope, prog, os.path.join(firmware_dir, f"simpleserial-aes-batch-{PLATFORM}.hex"))

    return scope, target

def collect(scope: cw.scope, target: cw.target, keys: np.ndarray, texts: np.ndarray, id: str, n: int):

    # Initialize output arrays
    trace_type = np.uint8 if scope.adc.bits_per_sample <= 8 else np.uint16
    t = np.zeros((scope.adc.samples, keys.shape[1]), dtype=trace_type)
    k = np.zeros((16, keys.shape[1]), dtype=np.uint8)
    pt = np.zeros((16, keys.shape[1]), dtype=np.uint8)
    
    # warmup
    for i in tqdm(range(0, 4*20, 4), desc="warming up", unit_scale=4):
        if i == 0:
            scope.arm()
        write = bytearray().join([bytearray(keys[..., i+j]) + bytearray(texts[..., i+j]) for j in range(min(4, keys.shape[1]-i))])
        for j in range(min(4, keys.shape[1]-i)):
            scope.capture()
            if j == 0:
                target.send_cmd(0x02, 0x00, write)

            scope.arm()
            tmp = scope.get_last_trace(as_int=True)

    # Collect data
    for i in tqdm(range(0, keys.shape[1], 4), desc="capturing traces", unit_scale=4):
        if i == 0:
            scope.arm()
        write = bytearray().join([bytearray(keys[..., i+j]) + bytearray(texts[..., i+j]) for j in range(min(4, keys.shape[1]-i))])
        for j in range(min(4, keys.shape[1]-i)):
            scope.capture()
            if j == 0:
                target.send_cmd(0x02, 0x00, write)

            scope.arm()
            tmp = scope.get_last_trace(as_int=True)
            t[..., i+j] = tmp
            k[..., i+j] = keys[..., i+j]
            pt[..., i+j] = texts[..., i+j]
        
    return t, k, pt

def _gen_dataset_tvla(n: int, seed: int = 42):

    n = int(np.ceil(n/3))
    
    rand = np.random.default_rng(seed=seed)
    k1 = np.asarray(bytearray(0x0123456789abcdef123456789abcdef0.to_bytes(16)), dtype=np.uint8).T
    k2 = k1
    pt1 = np.asarray(bytearray(0x00000000000000000000000000000000.to_bytes(16)), dtype=np.uint8).T
    pt2 = np.asarray(bytearray(0xda39a3ee5e6b4b0d3255bfef95601890.to_bytes(16)), dtype=np.uint8).T

    aes = Cipher(algorithms.AES128(bytearray(k1)), mode=modes.ECB())
    enc = aes.encryptor()

    d1k = np.broadcast_to(np.asarray(k1[:, None], dtype=np.uint8), (16, 2*n))
    d1pt = np.empty((16, 2*n), dtype=np.uint8)
    d2k = np.broadcast_to(np.asarray(k2[:, None], dtype=np.uint8), (16, n))
    d2pt = np.broadcast_to(np.asarray(pt2[:, None], dtype=np.uint8), (16, n))

    d1pt[..., 0] = pt1
    for i in range(1, d1pt.shape[1]):
        d1pt[..., i] = np.asarray(bytearray(enc.update(bytearray(d1pt[..., i-1])))).T

    # Shuffle dataset
    dk = np.hstack([d1k, d2k])
    dpt = np.hstack([d1pt, d2pt])
    shuffle_idx = rand.permutation(dk.shape[1])
    dk = dk[..., shuffle_idx]
    dpt = dpt[..., shuffle_idx]

    return dk, dpt

def _gen_dataset_random(n: int, seed: int = 21):
    rand = np.random.default_rng(seed=seed)
    keys = rand.integers(low=0, high=256, size=(16, n), dtype=np.uint8)
    texts = rand.integers(low=0, high=256, size=(16, n), dtype=np.uint8)
    return keys, texts

def main():

    dataset_funcs = {'random' : _gen_dataset_random, 'tvla' : _gen_dataset_tvla}

    parser = ArgumentParser('SCA Portability Dataset Collection')
    parser.add_argument('-d', '--device-id', type=str, required=True, dest='id')
    parser.add_argument('-t', '--type', type=str, required=True, dest='type', choices=list(dataset_funcs.keys()))
    parser.add_argument('-n', '--n-traces', type=int, required=False, default=50000, dest='n_traces')
    parser.add_argument('--delay', type=int, required=False, default=1e4, dest='delay')

    args = parser.parse_args()
    args.n_traces = args.n_traces + (args.n_traces % 4)

    # connect to device
    scope, target = connect_nano(args.delay)
    # scope, target = _connect_husky(args.delay)
    scope.adc.bits_per_sample
    
    # generate dataset
    print(f"generating {args.type} dataset...\n")
    dk, dpt = dataset_funcs[args.type](args.n_traces)
    
    # collect dataset
    t, k, pt = collect(scope, target, dk, dpt, args.id, args.n_traces)
    
    # export formatted dataset
    dset = Dataset.from_data(
        path=f"Device {args.id} {t.shape[1]} {args.type} Traces",
        traces=t, texts=pt, keys=k, metadata={
            'name' : f"Device {args.id} dataset. {t.shape[1]} {args.type} traces.",
            'scope' : "ChipWhisperer Nano",
            'DUT' : "STM32F0",
            'device_id' : args.id
        }
    )
    dset.save()

    print(f"exported dataset to {os.path.abspath(dset._path)}")

if __name__ == "__main__":
    main()
