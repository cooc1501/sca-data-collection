import chipwhisperer as cw
# import tensorflow
import subprocess
import os.path
from typing import Literal
import numpy as np
import cProfile
import io
from pstats import SortKey
import pstats
from tqdm import tqdm

## Chipwhisperer Board Set Up ##
'''Board Info:
    PLATFORM: CW308_STM32F3
    SCOPETYPE: OPENADC
    SS_VER: SS_VER_2_1
    CRYPTO_TARGET: TINYAES128C'''

x = cw.ktp.Basic()

class CW_Board():
    def __init__(self, platform, scopetype, ss_ver, crypto_target):
        self.scope = None
        self.target = None

        self.platform = platform.upper()
        self.scopetype = scopetype.upper()
        self.ss_ver = ss_ver.upper()
        self.crypto_target = crypto_target.upper()

        # Set Programmer
        if "STM" in platform or platform == "CWLITEARM" or platform == "CWNANO":
            self.prog = cw.programmers.STM32FProgrammer
        elif platform == "CW303" or platform == "CWLITEXMEGA":
            self.prog = cw.programmers.XMEGAProgrammer
        elif "neorv32" in platform.lower():
            self.prog = cw.programmers.NEORV32Programmer
        elif platform == "CW308_SAM4S" or platform == "CWHUSKY":
            self.prog = cw.programmers.SAM4SProgrammer
        else:
            self.prog = None

        # Set Target Type
        try:
            if self.ss_ver == "SS_VER_2_1":
                self.target_type = cw.targets.SimpleSerial2
            elif self.ss_ver == "SS_VER_2_0":
                raise OSError("SS_VER_2_0 is deprecated. Use SS_VER_2_1")
            else:
                self.target_type = cw.targets.SimpleSerial
        except:
            self.ss_ver = "SS_VER_1_1"
            self.target_type = cw.targets.SimpleSerial

        # Initialize KTP
        # self.ktp = cw.ktp.Basic()
        # self.ktp.fixed_key = True

    def set_ktp_generator(self, ktp):
        self.ktp = ktp

    def connect(self):
        self.scope = cw.scope()
        try:
            self.target = cw.target(self.scope, self.target_type)
        except:
            print("INFO: Caught exception on reconnecting to target - attempting to reconnect to scope first.")
            print(
                "INFO: This is a work-around when USB has died without Python knowing. Ignore errors above this line.")
            self.scope = cw.scope()
            self.target = cw.target(self.scope, self.target_type)
        self.scope.default_setup()

    def disconnect(self):
        self.scope.dis()
        self.target.dis()

    def update_scope_firmware(self):
        if self.scope.latest_fw_str > self.scope.fw_version_str:
            self.scope.upgrade_firmware()

    def flash_target(self, firmware: str = None):
        if firmware is None:
            firmware_path = "target-firmware/simpleserial-aes-{}.hex".format(self.platform.upper())
        else:
            firmware_path = os.path.join("target-firmware/", firmware)
        if not os.path.isfile(firmware_path):
            build_firmware(self)
        try:
            cw.program_target(self.scope, self.prog, firmware_path)
        except Exception as e:
            print("failed to flash target board with existing firmware: {}".format(e))

    def aes_batch(self, keys: list[bytearray], plaintexts: list[bytearray], samples: int = 2000):
        n_keys = len(keys)
        n_texts = len(plaintexts)

        t = np.empty((len(keys), samples), dtype=np.int16)
        k = np.empty((len(keys), 16), dtype=np.uint8)
        pt = np.empty((len(keys), 16), dtype=np.uint8)

        if n_keys % 4 != 0:
           keys.append(bytearray(16) for _ in range(len(keys)%4))
        if n_texts % 4 != 0:
           plaintexts.append(bytearray(16) for _ in range(len(plaintexts)%4))
        
        self.scope.adc.segments = 4
        self.scope.adc.samples = samples
        for i in tqdm(range(0, n_keys, 4), desc="capturing...", unit_scale=4):
            self.scope.arm()
            write = keys[i] + plaintexts[i] + keys[i+1] + plaintexts[i+1] + keys[i+2] + plaintexts[i+2] + keys[i+3] + plaintexts[i+3]
            # self.target.simpleserial_write(2, write)
            self.target.send_cmd(0x02, 0x00, write)
            self.scope.capture(poll_done=True)
            tmp = self.scope.get_last_trace(as_int=True)
            for j in range(4):
                t[i+j] = tmp[samples*j:samples*(j+1)]
                k[i+j] = keys[i+j]
                pt[i+j] = plaintexts[i+j]
        
        return t, k, pt

        
        

            
        

    def set_key(self, key):
        self.ktp.setInitialKey(key)
        temp_key, pt = self.ktp.next()
        self.target.set_key(temp_key)
        # make sure this updates the key if it's already initialized

    def record_trace(self, key, pt):
        # pr = cProfile.Profile()
        # pr.enable()

        self.scope.arm()
        self.target.simpleserial_write('p', pt)

        ret = self.scope.capture()
        if ret:
            print("Target timed out!")

        response = self.target.simpleserial_read('r', 16)
        trace = self.scope.get_last_trace(as_int=False)

        # pr.disable()
        # s = io.StringIO()
        # sortby = SortKey.CUMULATIVE
        # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # print(s.getvalue())
        return trace, key, pt

    def record_from_ktp(self):
        traces = np.empty((self.ktp.count, self.scope.adc.samples), dtype=np.uint16)
        keys = np.empty((self.ktp.count, 16), dtype=np.uint8)
        plaintexts = np.empty((self.ktp.count, 16), dtype=np.uint8)

        # self.scope.adc.segments = self.ktp.count
        # self.scope.adc.segment_cycle_counter_en = False

        for i, (k, pt) in tqdm(enumerate(self.ktp), desc='capturing traces', total=self.ktp.count):
            self.scope.arm()
            self.target.simpleserial_write('p', pt)

            ret = self.scope.capture()
            if ret:
                print("Target timed out!")

            response = self.target.simpleserial_read('r', 16)
            traces[i] = self.scope.get_last_trace(as_int=True)
            keys[i] = k
            plaintexts[i] = pt

        return traces, keys, plaintexts



def build_firmware(board: CW_Board):
    os.chdir("/home/george/Research/chipwhisperer/hardware/victims/firmware/simpleserial-aes")
    # Build AES Firmware
    os.system("cd /home/george/Research/chipwhisperer/hardware/victims/firmware/simpleserial-aes")
    subprocess.run(["make", "PLATFORM={}".format(board.platform.upper()),
                    "CRYPTO_TARGET={}".format(board.crypto_target.upper()), "SS_VER={}".format(board.ss_ver.upper())])

    # Copy to working directory
    subprocess.Popen(["cp",
                      "/home/george/Research/chipwhisperer/hardware/victims/firmware/simpleserial-aes/simpleserial-aes-{}.hex".format(
                          board.platform.upper()),
                      "target-firmware/simpleserial-aes-{}.hex".format(board.platform.upper())],
                     cwd="/home/george/Research/CNN-Profiling-Attack/cnn-profiling-attack")


def random_key(first_byte):
    if not (0 <= first_byte <= 255):
        raise ValueError("first_byte must be between 0 and 255 (inclusive).")

    random_bytes = os.urandom(15)

    full_bytes = bytes([first_byte]) + random_bytes

    return full_bytes.hex()


## Data Organization ##
dataset_path = ""  # If program is run from /src and recorded-data is in root, main_data_path = "../"


def set_main_data_path(path: str = ""):
    global dataset_path
    dataset_path = path

def trace_path(board: CW_Board, key_byte_zero):
    # if not os.path.isdir("recorded-data/{}/traces/")
    trace_path = "{}{}/traces/{}".format(dataset_path, board.platform, hex(key_byte_zero))
    return trace_path


def profile_path(board: CW_Board, key_byte_zero):
    profile_path = "{}{}/profiles/{}".format(dataset_path, board.platform, hex(key_byte_zero))
    return profile_path


def model_path(board: CW_Board):
    profile_path = "{}{}/profiles/".format(dataset_path, board.platform)
    return profile_path


def prediction_path(board: CW_Board, model_name: str):
    prediction_path = "{}{}/profiles/{}_predictions".format(dataset_path, board.platform, model_name)
    return prediction_path


valid_data_types = ["profile_path", "trace_path", "model_path", "prediction_path"]
def check_path(board: CW_Board, key_byte_zero = None, data_type: str = None, model_name: str = None):
    if data_type not in valid_data_types:
        raise ValueError("Invalid data type to store, valid data types are: {}".format(valid_data_types))
    elif data_type == "profile_path":
        if not os.path.isdir(profile_path(board, key_byte_zero)):
            return False
        else:
            return profile_path(board, key_byte_zero)
    elif data_type == "trace_path":
        if not os.path.isdir(trace_path(board, key_byte_zero)):
            return False
        else:
            return trace_path(board, key_byte_zero)
    elif data_type == "model_path":
        if not os.path.isdir(model_path(board)):
            return False
        else:
            return model_path(board)
    elif data_type == "prediction_path":
        if not os.path.isdir(prediction_path(board, model_name)):
            return False
        else:
            return prediction_path(board, model_name)


def check_make_path(board: CW_Board, key_byte_zero=None, data_type: str = None, model_name: str = None):
    if data_type not in valid_data_types:
        raise ValueError("Invalid data type to store, valid data types are: {}".format(valid_data_types))
    elif data_type == "profile_path":
        if not os.path.isdir(profile_path(board, key_byte_zero)):
            os.makedirs(profile_path(board, key_byte_zero))
        return profile_path(board, key_byte_zero)
    elif data_type == "trace_path":
        if not os.path.isdir(trace_path(board, key_byte_zero)):
            os.makedirs(trace_path(board, key_byte_zero))
        return trace_path(board, key_byte_zero)
    elif data_type == "model_path":
        if not os.path.isdir(model_path(board)):
            os.makedirs(model_path(board))
        return model_path(board)
    elif data_type == "prediction_path":
        if not os.path.isdir(prediction_path(board, model_name)):
            os.makedirs(prediction_path(board, model_name))
        return prediction_path(board, model_name)


def trace_filename(key_byte_zero, num_traces):
    return hex(key_byte_zero) + "-" + str(num_traces) + ".npz"


def save_traces(board: CW_Board, key_byte_zero, num_traces, trace_array, textin_array):
    # check path -> save trace array and textin array as npz
    check_make_path(board, key_byte_zero, "trace_path")
    np.savez(trace_path(board, key_byte_zero) + "/" + trace_filename(key_byte_zero, num_traces),
             np.asarray(trace_array), np.asarray(textin_array))


def load_traces(board: CW_Board, key_byte_zero, num_traces):
    path = check_path(board, key_byte_zero, "trace_path")
    if not path:
        raise FileNotFoundError("No traces found for dataset {}".format(board.platform))
    full_path = path + "/" + trace_filename(key_byte_zero, num_traces)
    if path and os.path.isfile(full_path):
        load = np.load(full_path)
        return load['arr_0'], load['arr_1']
    else:
        raise FileNotFoundError("Could not load traces from {}".format(full_path))


def load_model(board: CW_Board, model_name: str):
    path = check_path(board, model_name, "model_path")
    full_path = path + "/" + model_name + "_full_model.keras"
    if os.path.isfile(full_path):
        return tf.keras.models.load_model(full_path)
    else:
        raise FileNotFoundError("Could not load model from {}".format(full_path))


def save_predictions(board: CW_Board, model_name: str, predictions: np.ndarray):
    path = check_make_path(board, model_name, "prediction_path")
    np.save(path + "/predictions.npy", predictions)


## Recording Traces ##
def record_traces(board: CW_Board, key, num_traces):
    trace_array = []
    textin_array = []
    board.set_key(key)
    for trace in range(num_traces):
        trace, pt = board.record_trace()
        trace_array.append(trace)
        textin_array.append(pt)
    return trace_array, textin_array
