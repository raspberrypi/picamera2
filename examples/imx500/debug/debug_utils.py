import time

from picamera2 import CompletedRequest


class FPSCounter:
    def __init__(self, name):
        self.name = name
        self.reset()

    def reset(self):
        self.start_time = time.time()
        self.frame_count = 0
        self.fps = 0

    def update(self):
        self.frame_count += 1
        elapsed_time = time.time() - self.start_time
        if elapsed_time > 1.0:
            self.fps = self.frame_count / elapsed_time
            self.start_time = time.time()
            self.frame_count = 0
        return None

    def print(self, print_text=True):
        t = f"{self.name}: {self.fps:.2f}"
        if print_text:
            print(t)
        return t


camera_fps_counter = FPSCounter("FPS")
output_fps_counter = FPSCounter("DPS")
input_tensor_counter = FPSCounter("IPS")

row_count = 0
d_result = []
i_result = []
timestamps = []
dnn_runtime_result = []
dsp_runtime_result = []
get_meta_time = []


def debug_fps(request: CompletedRequest, imx500, check_input=False, verbose=True, kpi=True, skip_metadata=False):
    """ print statistics on the performance"""
    if skip_metadata:
        camera_fps_counter.update()
        global row_count
        row_count += 1
        if row_count >= 30:
            camera_fps_counter.print()
            camera_fps_counter.reset()
            row_count = 0
        return
    global d_result, i_result, timestamps, dnn_runtime_result, dsp_runtime_result, get_meta_time
    s = time.time()
    metadata = request.get_metadata()
    e = time.time()
    get_meta_time.append(round((e - s) * 1000, 2))
    camera_fps_counter.update()
    output_found = "CnnOutputTensor" in metadata
    if output_found:
        output_fps_counter.update()
        d_result.append("s")
    else:
        d_result.append("f")
    current_timestamp = metadata.get("SensorTimestamp")
    kpi_info = imx500.get_kpi_info(metadata)
    if kpi_info is not None:
        dnn_runtime_result.append(kpi_info[0])
        dsp_runtime_result.append(kpi_info[1])
    else:
        dnn_runtime_result.append(None)
        dsp_runtime_result.append(None)
    timestamps.append(current_timestamp)
    input_found = "CnnInputTensor" in metadata
    i_result.append("s" if input_found else "f")
    if input_found:
        input_tensor_counter.update()
    if check_input and output_found != input_found:
        print(f"ERROR: SensorTimestamp: {current_timestamp} input: {input_found}, output: {output_found}")
    if len(d_result) >= 30:
        text = "\n" + "-" * 20 + "\n"
        if verbose:
            text += camera_fps_counter.print(False) + "\n"
            text += output_fps_counter.print(False) + "\n"
            if check_input:
                text += input_tensor_counter.print(False) + "\n"
            d_sum_fail = len([r for r in d_result if r == "f"])
            d_sum_sec = len(d_result) - d_sum_fail
            text += "Detections:    " + "".join(d_result) + f" success: {d_sum_sec}, fails: {d_sum_fail}" + "\n"
            if check_input:
                i_sum_fail = len([r for r in i_result if r == "f"])
                i_sum_sec = len(i_result) - i_sum_fail
                text += "Input tensors: " + "".join(i_result) + f" success: {i_sum_sec}, fails: {i_sum_fail}" + "\n"
            start_index = 0 if len(timestamps) == 30 else 1
            text += f"SensorTimestamp: {timestamps[start_index:]}" + "\n"
            text += f"get metadata: {get_meta_time}" + "\n"
        diffs = [((timestamps[i] - timestamps[i - 1]) / 10 ** 6) for i in range(1, len(timestamps))]
        diffs_min = min(diffs)
        diffs_max = max(diffs)
        if len(timestamps) == 30:
            diffs = ["NA"] + diffs
        text += f"SensorTimestamp diffs: min: {diffs_min}, max: {diffs_max}, {diffs}" + "\n"
        if kpi:
            clean_dnn = [r for r in dnn_runtime_result if r is not None]
            min_dnn = min(clean_dnn) if len(clean_dnn) > 0 else "NA"
            max_dnn = max(clean_dnn) if len(clean_dnn) > 0 else "NA"
            clean_dps = [r for r in dsp_runtime_result if r is not None]
            min_dsp = min(clean_dps) if len(clean_dps) > 0 else "NA"
            max_dsp = max(clean_dps) if len(clean_dps) > 0 else "NA"
            text += f"DNN runtime: Min: {min_dnn}, Max: {max_dnn}, {dnn_runtime_result}" + "\n"
            text += f"DSP runtime: Min: {min_dsp}, Max: {max_dsp}, {dsp_runtime_result}" + "\n"
        print(text)
        d_result = []
        i_result = []
        timestamps = [timestamps[-1]]
        dnn_runtime_result = []
        dsp_runtime_result = []
        get_meta_time = []
