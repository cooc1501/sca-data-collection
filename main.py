import chipwhisperer as cw
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import numpy as np
import cwtools as cwt
from tqdm import tqdm
import os

import matplotlib.pyplot as plt

from dataset import Dataset

def tvla(n: int):
    k1 = bytearray(0x0123456789abcdef123456789abcdef0.to_bytes(16))
    k2 = k1
    pt1 = bytearray(0x00000000000000000000000000000000.to_bytes(16))
    pt2 = bytearray(0xda39a3ee5e6b4b0d3255bfef95601890.to_bytes(16))

    aes = Cipher(algorithms.AES128(k1), mode=modes.ECB())
    enc = aes.encryptor()

    # keys, plaintexts
    d1 = (np.broadcast_to(np.asarray(k1, dtype=np.uint8), (2*n, 16)), np.empty((2*n, 16), dtype=np.uint8))
    # d2 = (np.empty((n, 16), dtype=np.uint8), np.empty((n, 16), dtype=np.uint8))
    d2 = (np.broadcast_to(np.asarray(k2, dtype=np.uint8), (n, 16)), np.broadcast_to(np.asarray(pt2, dtype=np.uint8), (n, 16)))
    d1[1][0] = np.asarray(pt1, dtype=np.uint8)
    for i in range(1, 2*n):
        d1[1][i] = bytearray(enc.update(d1[1][i-1]))
    
    return d1, d2

def tvla_mixed(n: int):
    d1, d2 = tvla(n)
    d3k = np.empty((d1[0].shape[0] + d2[0].shape[0], 16), dtype=np.uint8)
    d3pt = np.empty((d1[1].shape[0] + d2[1].shape[0], 16), dtype=np.uint8)
    d3k = np.vstack((d1[0], d2[0]))
    d3pt = np.vstack((d1[1], d2[1]))
    rng = np.random.default_rng()
    shuffle_idx = rng.permutation(d3k.shape[0])
    d3k = d3k[shuffle_idx]
    d3pt = d3pt[shuffle_idx]

    return d3k, d3pt



class TvlaGen:
    def __init__(self, n: int):
        self.count = n
        d1, d2 = tvla(self.count)
        # intersperse the datasets
        self.d3k = np.empty((d1[0].shape[0] + d2[0].shape[0], 16), dtype=np.uint8)
        self.d3pt = np.empty((d1[1].shape[0] + d2[1].shape[0], 16), dtype=np.uint8)
        self.d3k = np.vstack((d1[0], d2[0]))
        self.d3pt = np.vstack((d1[1], d2[1]))
        rng = np.random.default_rng()
        shuffle_idx = rng.permutation(self.d3k.shape[0])
        self.d3k = self.d3k[shuffle_idx]
        self.d3pt = self.d3pt[shuffle_idx]

        self.count = self.d3k.shape[0]
    
    def __iter__(self):
        for i in range(self.d3k.shape[0]):
            yield (self.d3k[i], self.d3pt[i])


def tvla_gen(n: int):
    d1, d2 = tvla(n)
    # intersperse the datasets
    d3k = np.empty((d1[0].shape[0] + d2[0].shape[0], 16), dtype=np.uint8)
    d3pt = np.empty((d1[1].shape[0] + d2[1].shape[0], 16), dtype=np.uint8)
    d3k = np.vstack((d1[0], d2[0]))
    d3pt = np.vstack((d1[1], d2[1]))
    rng = np.random.default_rng()
    shuffle_idx = rng.permutation(d3k.shape[0])
    d3k = d3k[shuffle_idx]
    d3pt = d3pt[shuffle_idx]

    for i in range(d3k.shape[0]):
        yield (d3k[i], d3pt[i])
    

        

def main():
    # Setup CW Husky
    # scope = cw.scope()
    connected_board = cwt.CW_Board("CWHUSKY", "OPENADC", "SS_VER_2_1", "TINYAES128C")
    connected_board.connect()


    connected_board.flash_target("/home/george/research-local/sca-suite/chipwhisperer/firmware/mcu/simpleserial-aes-batch/simpleserial-aes-batch-CWHUSKY.hex")
    captures = 50000
    keys = [bytearray(os.urandom(16)) for _ in range(captures)]
    plaintexts = [bytearray(os.urandom(16)) for _ in range(captures)]

    # keys, plaintexts = tvla_mixed(50)

    traces, keys, plaintexts = connected_board.aes_batch(keys, plaintexts, samples=5000)

    # n = 100000

    # connected_board.set_ktp_generator(TvlaGen(n))
    # traces, keys, plaintexts = connected_board.record_from_ktp()

    md = {
        'name' : 'Microchip SAM4S Random 50K',
        "target": "Microchip ATSAM4S2A ChipWhisperer target board running tiny-aes-128 firmware", 
        "scope": "ChipWhisperer Husky", 
        "description": "Random key, random plaintext"
    }
    dset = Dataset.from_data('SAM4S_Random_50K', traces, plaintexts, keys, md)
    dset.save()
    return

    # np.save('traces.npy', traces)
    # np.save('keys.npy', keys)
    # np.save('plaintexts.npy', plaintexts)

    plt.plot(np.arange(traces.shape[1]), np.mean(traces, axis=0))
    plt.show()

    # for k, pt in tqdm(tvla_gen(n), desc='capturing_traces', total=n*3):
        # t, k, pt = connected_board.record_trace(k, pt)

    # connected_board.disconnect()


    # ktp=tvla_gen(100000)
    # for k, pt in ktp:
    #     print(k, " ", pt)
    # pass

    return



if __name__ == "__main__":
    main()