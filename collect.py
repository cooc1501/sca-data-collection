import os
from argparse import ArgumentParser
import subprocess

import chipwhisperer as cw
import numpy as np
from tqdm import tqdm
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from dataset import Dataset


def connect():
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
    ret = subprocess.run(["make", f"PLATFORM={PLATFORM}", f"CRYPTO_TARGET={CRYPTO_TARGET}", f"SS_VER={SS_VER}"], cwd=firmware_dir)
    cw.program_target(scope, prog, os.path.join(firmware_dir, "simpleserial-aes-batch-CWNANO.hex"))
    
    return scope, target

def connect_husky():
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
    ret = subprocess.run(["make", f"PLATFORM={PLATFORM}", f"CRYPTO_TARGET={CRYPTO_TARGET}", f"SS_VER={SS_VER}"], cwd=firmware_dir)
    cw.program_target(scope, prog, os.path.join(firmware_dir, f"simpleserial-aes-batch-{PLATFORM}.hex"))

    return scope, target

def collect(scope, target, id: str, n: int):
    # Should each device use the same keys and plaintexts? probably
    keys = [bytearray(os.urandom(16)) for _ in range(n)]
    plaintexts = [bytearray(os.urandom(16)) for _ in range(n)]

    # Initialize output arrays
    t = np.empty((len(keys), scope.adc.samples), dtype=np.uint16)  # TODO: make this uint8 for nano
    k = np.empty((len(keys), 16), dtype=np.uint8)
    pt = np.empty((len(keys), 16), dtype=np.uint8)
    
    # Collect data
    for i in tqdm(range(0, n, 4), desc="capturing", unit_scale=4):
        scope.arm()
        write = keys[i] + plaintexts[i] + keys[i+1] + plaintexts[i+1] + keys[i+2] + plaintexts[i+2] + keys[i+3] + plaintexts[i+3]
        target.send_cmd(0x02, 0x00, write)
        for j in range(4):
            scope.capture()
            tmp = scope.get_last_trace(as_int=True)
            t[i+j] = tmp
            k[i+j] = keys[i+j]
            pt[i+j] = plaintexts[i+j]

    # Export formatted dataset
    dset = Dataset.from_data(
        path=f"Device {id} {n} Traces",
        traces=t, texts=pt, keys=k, metadata={
            'name' : f"Device {id} dataset. {n} traces.",
            'scope' : "ChipWhisperer Nano",
            'DUT' : "STM32F0",
            'device_id' : id
        }
    )
    dset.save()

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

    return dk, dpt, shuffle_idx

def _gen_dataset_random(n: int, seed: int = 21):
    rand = np.random.default_rng(seed=seed)
    keys = rand.integers(low=0, high=256, size=(16, n), dtype=np.uint8)
    texts = rand.integers(low=0, high=256, size=(16, n), dtype=np.uint8)
    return keys, texts

# Ok I actually think this is going to work. I just need to decide what datasets I want
# collected. I'll generate some (or make some deterministic functions to generate them)
# and include them in the repository.

def main():
    parser = ArgumentParser('SCA Portability Dataset Collection')
    parser.add_argument('-d', '--device-id', type=str, required=True, dest='id')
    parser.add_argument('-n', '--n-traces', type=int, required=False, default=50000, dest='n_traces')
    
    args = parser.parse_args()

    # Connect to device
    # scope = connect()
    dk, dpt, shuffle_idx = _gen_dataset_tvla(50000)
    dk2, dpt2, shuffle_idx2 = _gen_dataset_tvla(50000)
    assert((dk == dk2).all(), "dataset non-deterministic")
    assert((dpt == dpt2).all(), "dataset non-deterministic")
    assert((shuffle_idx == shuffle_idx2).all(), "dataset non-deterministic")

    dk, dpt = _gen_dataset_random(50000)
    dk2, dpt2 = _gen_dataset_random(50000)
    assert((dk == dk2).all(), "dataset non-deterministic")
    assert((dpt == dpt2).all(), "dataset non-deterministic")

    # scope, target = connect_husky()
    # collect(scope, target, args.id, args.n_traces)

if __name__ == "__main__":
    main()
