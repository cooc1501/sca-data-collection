from tqdm import tqdm
import os
from argparse import ArgumentParser
import subprocess

import chipwhisperer as cw

from dataset import Dataset


def connect() -> tuple[cw.scope, cw.target]:
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

    # Build and Flash firmware
    firmware_dir = os.path.join(os.path.dirname(__file__), 'chipwhisperer/firmware/mcu/simpleserial-aes-batch')
    ret = subprocess.run(["make", f"PLATFORM={PLATFORM}", f"CRYPTO_TARGET={CRYPTO_TARGET}", f"SS_VER={SS_VER}"], cwd=firmware_dir)
    cw.program_target(scope, prog, os.path.join(firmware_dir, "simpleserial-aes-batch-CWNANO.hex"))

    return scope, target


def collect(id: str, n: int):
    # Should each device use the same keys and plaintexts? probably
    ...

def main():
    parser = ArgumentParser('SCA Portability Dataset Collection')
    parser.add_argument('-d', '--device-id', type=str, required=True, dest='id')
    parser.add_argument('-n', '--n-traces', type=int, required=False, default=50000, dest='n_traces')
    
    args = parser.parse_args()

    # Connect to device
    scope = connect()
    collect(args.id, args.n_traces)

if __name__ == "__main__":
    main()
