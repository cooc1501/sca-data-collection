import numpy as np
import os
import json

"""
Class to handle the storage and access of datasets.
"""
class Dataset:
    def __init__(self, path: str):
        self._traces: np.ndarray
        self._texts: np.ndarray
        self._keys: np.ndarray | None = None

        self._path: str = path

        self.metadata: dict | None = None

    # Class Methods
    @classmethod
    def load(cls, path: str):
        dset = cls(path)
        dset.traces = np.load(os.path.join(path, 'traces.npy'))
        dset.texts = np.load(os.path.join(path, 'texts.npy'))
        if os.path.isfile(os.path.join(path, 'keys.npy')):
            dset.keys = np.load(os.path.join(path, 'keys.npy'))
        
        if os.path.isfile(os.path.join(path, 'metadata.json')):
            with open(os.path.join(path, 'metadata.json'), 'r') as f:
                dset.metadata = json.load(f)
        
        return dset

    @classmethod
    def from_data(cls, path: str, traces: np.ndarray, texts: np.ndarray,
                  keys: np.ndarray | None = None, metadata: dict | None = None):
        dset = cls(path)
        dset.traces = traces
        dset.texts = texts
        dset.keys = keys
        dset.metadata = metadata
        
        return dset

    def save(self):
        if not os.path.isdir(self._path):
            os.makedirs(self._path)
        np.save(os.path.join(self._path, 'traces.npy'), self.traces)
        np.save(os.path.join(self._path, 'texts.npy'), self.texts)

        if type(self._keys) == np.ndarray:
            np.save(os.path.join(self._path, 'keys.npy'), self._keys)

        if self.metadata != None:
            with open(os.path.join(self._path, 'metadata.json'), 'w') as f:
                json.dump(self.metadata, f)

    def get_traces(self):
        return self._traces

    def set_traces(self, traces: np.ndarray):
        self._traces = traces

    traces = property(get_traces, set_traces)

    def get_texts(self) -> np.ndarray:
        return self._texts

    def get_texts_bytes(self) -> list[bytes]:
        return [bytes.fromhex(''.join(f"{x:02x}" for x in self._texts[i])) for i in range(self._texts.shape[0])]

    def set_texts(self, texts: np.ndarray | list[bytes]):
        if type(texts) == np.ndarray:
            self._texts = texts
        elif type(texts) == list[bytes]:
            self._texts = np.vstack([np.asarray(list(text), dtype=np.uint8) for text in texts])
        else:
            raise TypeError("texts must be numpy array or list of bytes")

    texts = property(get_texts, set_texts)
    texts_bytes = property(get_texts_bytes, set_texts)

    def get_keys(self) -> np.ndarray:
        return self._keys

    def get_keys_bytes(self) -> list[bytes]:
        return [bytes.fromhex(''.join(f"{x:02x}" for x in self._keys[i])) for i in range(self._keys.shape[0])]

    def set_keys(self, keys: np.ndarray | list[bytes] | None):
        if type(keys) == np.ndarray:
            self._keys = keys
        elif type(keys) == list[bytes]:
            self._keys = np.vstack([np.asarray(list(key), dtype=np.uint8) for key in keys])
        elif keys == None:
            self._keys = None
        else:
            raise TypeError("keys must be numpy array or list of bytes")

    keys = property(get_keys, set_keys)
    keys_bytes = property(get_keys_bytes, set_keys)