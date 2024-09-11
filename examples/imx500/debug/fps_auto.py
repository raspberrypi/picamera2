"""
Automation for running multiple models on the imx500 to collect statistics on the performance
with difference configurations and models
best for get data on batch of models - running can take a few hours
"""
import argparse
import datetime
import json
import multiprocessing
import os
import time
import cv2


from picamera2 import Picamera2
from debug_utils import FPSCounter
from picamera2.devices import IMX500

d_result = []
postprocess_take = []

stop = False
fps = FPSCounter("fps")
dps = FPSCounter("dsp")
kpi = None
imx500: IMX500 = None
picam2: Picamera2 = None
output_found_metadata = None

from examples.imx500.imx500_classification_demo import parse_and_draw_classification_results as c_p
from examples.imx500.imx500_object_detection_demo import parse_and_draw_detections as od_p
from examples.imx500.imx500_pose_estimation_yolov8n_demo import picamera2_pre_callback as pose_yolov8n_p
from examples.imx500.imx500_pose_estimation_higherhrnet_demo import picamera2_pre_callback as post_higher_p
from examples.imx500.imx500_segmentation_demo import create_and_draw_masks as seg_p
from examples.imx500.imx500_pose_estimation_yolov8n_demo import get_drawer as yolov8n_get_drawer
from examples.imx500.imx500_pose_estimation_higherhrnet_demo import get_drawer as higher_get_drawer

postprocess = {
    "classification": c_p,
    "object_detection": od_p,
    "yolov8n_pose": pose_yolov8n_p,
    "higherhrnet_coco": post_higher_p,
    "segmentation": seg_p
}

nets = {
    "efficientnet_bo": "classification",
    "efficientnet_lite0": "classification",
    "efficientnetv2_b0": "classification",
    "efficientnetv2_b1": "classification",
    "efficientnetv2_b2": "classification",
    "levit_128s": "classification",
    "mnasnet1.0": "classification",
    "mobilenet_v2": "classification",
    "mobilevit_xs": "classification",
    "mobilevit_xxs": "classification",
    "regnetx_002": "classification",
    "regnety_002": "classification",
    "regnety_004": "classification",
    "resnet18": "classification",
    "shufflenet_v2_x1_5": "classification",
    "squeezenet1.0": "classification",
    "yolov8n_inst_seg": "instance_segmentation",
    "higherhrnet_coco": "higherhrnet_coco",
    "yolov8n_pose": "yolov8n_pose",
    "efficientdet_lite0": "object_detection",
    "efficientdet_lite0_pp": "object_detection",
    "nanodet_plus_416x416": "object_detection",
    "nanodet_plus_416x416_pp": "object_detection",
    "ssd_mobilenetv2_fpnlite_320x320_pp": "object_detection",
    "yolov5n": "object_detection",
    "yolov8n": "object_detection",
    "yolov8n_pp": "object_detection",
    "deeplabv3plus": "segmentation"
}

object_detection_custom_post = {
    "yolov8n": "yolov8n",
    "yolov5n": "yolov5n",
    "nanodet_plus_416x416": "nanodet",
    "efficientdet_lite0": "efficientdet_lite0"

}

net_names = set(nets.keys())


class Args:

    def __init__(self, type):
        if type == "classification":
            self.labels = "assets/imagenet_labels.txt"
            self.softmax = True
            self.preserve_aspect_ratio = False
        elif type == "object_detection":
            self.labels = "assets/coco_labels.txt"
            self.bbox_normalization = False
            self.threshold = 0.55
            self.iou = 0.65
            self.max_detections = 10
            self.ignore_dash_labels = False
            self.preserve_aspect_ratio = False
            self.postprocess = ""
        elif type == "yolov8n_pose":
            self.labels = "assets/coco_labels.txt"
            self.box_min_confidence = 0.3
            self.keypoint_min_confidence = 0.3
            self.iou_threshold = 0.7
            self.max_out_dets = 300
        elif type == "higherhrnet_coco":
            self.labels = "assets/coco_labels.txt"
            self.detection_threshold = 0.3
        elif type == "instance_segmentation":
            self.score_threshold =0.1
            self.mask_threshold = 0.5
            self.iou_threshold = 0.7
            self.max_out_dets = 5
            self.labels = "assets/coco_labels.txt"

        else:
            raise ValueError(f"Unknown argument type: {type}")


def run_postprocess(request):
    global imx500, picam2, postprocess_take
    from examples.imx500 import (imx500_classification_demo,
                                 imx500_object_detection_demo,
                                 imx500_pose_estimation_yolov8n_demo,
                                 imx500_pose_estimation_higherhrnet_demo,
                                 imx500_segmentation_demo)
    l = (imx500_classification_demo,
         imx500_object_detection_demo,
         imx500_pose_estimation_yolov8n_demo,
         imx500_pose_estimation_higherhrnet_demo,
         imx500_segmentation_demo)
    for m in l:
        m.picam2 = picam2
        m.imx500 = imx500
    imx500_classification_demo.args = Args("classification")
    imx500_object_detection_demo.args = Args("object_detection")
    imx500_pose_estimation_yolov8n_demo.args = Args("yolov8n_pose")
    imx500_pose_estimation_higherhrnet_demo.args = Args("higherhrnet_coco")
    imx500_pose_estimation_yolov8n_demo.drawer = yolov8n_get_drawer()
    imx500_pose_estimation_higherhrnet_demo.drawer = higher_get_drawer()

    post_func = None
    for net_name in net_names:
        if (net_name + ".rpk") in model_path:
            post_func = postprocess[nets[net_name]]
            if net_name in object_detection_custom_post:
                imx500_object_detection_demo.args.postprocess = object_detection_custom_post[net_name]
            break
    if post_func is None:
        print(f"No postprocessing found for {model_path}")
        postprocess_take.append(0)
    else:
        s = time.time()
        post_func(request)
        e = time.time()
        postprocess_take.append(round(((e - s) * 1000), 2))


def preprocess_callback(request):
    global d_result, stop, kpi, imx500, output_found_metadata
    metadata = request.get_metadata()
    output_found = "CnnOutputTensor" in metadata
    if args.postprocess:
        run_postprocess(request)
    fps.update()
    if output_found:
        dps.update()
        d_result.append("s")
        kpi = imx500.get_kpi_info(metadata)
        output_found_metadata = metadata
    else:
        d_result.append("f")
    if len(d_result) >= 60:
        stop = True
    if args.mode == "only_output" and output_found:
        stop = True


def get_output_load_time():
    global output_found_metadata
    if output_found_metadata is None or "CnnOutputTensor" not in output_found_metadata:
        return "NA"
    res = []
    for _ in range(10):
        s = time.time()
        _ = imx500.get_outputs(metadata=output_found_metadata)
        e = time.time()
        res.append(round((e - s) * 1000, 2))

    return f"~{min(res)}-{max(res)} ms"


def extract_name(path):
    filename = os.path.basename(path)
    name, ext = os.path.splitext(filename)
    if "imx500_network_" in name:
        name = name.replace("imx500_network_", "")
    return name


def run_model(model_path):
    global imx500
    print(f"Model: {model_path}")

    imx500 = IMX500(model_path)
    if args.mode == "search":
        run_search(model_path)
    elif args.mode == "all":
        run_all()
    elif args.mode == "only_output":
        run_with_fps(1)
        set_res(1)
    else:
        raise ValueError(f"unknown mode: {args.mode}")


def run_all():
    global d_result
    start = 1
    end = 30
    for user_fps in range(start, end + 1):
        run_with_fps(user_fps)
        zero_res = "s" not in d_result[-30:]
        set_res(user_fps)
        if zero_res:
            break


def run_search(model_path):
    global d_result
    user_fps = 30
    max_fps = 30
    min_fps = 1
    finish = False
    while not finish:
        run_with_fps(user_fps)
        print(user_fps, d_result[-30:])
        ok = "f" not in d_result[-30:]
        if ok and user_fps >= (max_fps - 1):
            set_res(user_fps)
            finish = True
        elif user_fps <= min_fps and not ok:
            set_res(user_fps)
            finish = True
        elif min_fps >= max_fps:
            finish = True
            set_res(user_fps)
        elif ok:
            min_fps = user_fps
            user_fps += max(1, (max_fps - min_fps) // 2)
        elif not ok:
            max_fps = user_fps
            user_fps -= max(1, (max_fps - min_fps) // 2)
        else:
            set_res(user_fps)
            assert False, f"file {model_path} not check "


def set_res(user_fps):
    global d_result, stop, kpi, fps, dps
    if os.path.exists(json_path):
        with open(json_path, 'r') as file:
            data = json.load(file)
    else:
        data = {}
    name = extract_name(model_path)
    if name not in data:
        data[name] = {}
    if user_fps not in data[name]:
        data[name][user_fps] = {}
    d = data[name][user_fps]
    d["user_fps"] = user_fps
    d["dnn_runtime"] = kpi[0] if kpi is not None else "NA"
    d["dsp_runtime"] = kpi[1] if kpi is not None else "NA"
    d["d"] = "".join(d_result)
    d["fps"] = f"{fps.fps:.2f}"
    d["dps"] = f"{dps.fps:.2f}"
    d["preview"] = SHOW_PREVIEW
    d['postprocess'] = args.postprocess
    d["loading_output"] = get_output_load_time()
    if args.postprocess:
        d["total_postprocess_time"] = f"~{min(postprocess_take)}-{max(postprocess_take)} ms"
    with open(json_path, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def run_with_fps(user_fps):
    global d_result, stop, kpi, fps, dps, picam2, postprocess_take
    d_result = []
    postprocess_take = []
    stop = False
    fps = FPSCounter("fps")
    dps = FPSCounter("dsp")
    kpi = None
    print(f"User defined FPS: {user_fps} Preview: {SHOW_PREVIEW}")
    picam2 = Picamera2()
    config = picam2.create_preview_configuration(controls={"FrameRate": user_fps}, buffer_count=28)
    s = time.time()
    picam2.start(config, show_preview=SHOW_PREVIEW)
    e = time.time()
    print(f"init take {(e - s):.2f} seconds")
    cv2.startWindowThread()
    time.sleep(10)
    picam2.pre_callback = preprocess_callback

    timeout = 10 * 60  # 10 minutes in seconds
    start_time = time.time()

    while not stop:
        time.sleep(1)
        elapsed_time = time.time() - start_time
        if elapsed_time > timeout:
            print("Timeout reached, restarting...")
            picam2.close()
            cv2.destroyAllWindows()
            run_with_fps(user_fps)
            return

    picam2.close()
    cv2.destroyAllWindows()


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rpk_folder", type=str, default="../networks", help="Path for rpk folder")
    parser.add_argument("--rpk", type=str, nargs='*', default=[], help="Paths for rpk files")
    parser.add_argument("--mode", choices=["all", "search", "only_output"], default="search", help="loop mode")
    parser.add_argument("--preview", action="store_true", help="Show preview window")
    parser.add_argument("--postprocess", action="store_true", help="run with post processing")
    parser.add_argument("--json-path", type=str, default="", help="Path for json path")
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    SHOW_PREVIEW = args.preview
    skip_models_names = []
    if args.json_path:
        json_path = args.json_path
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                data = json.load(f)
            skip_models_names = list(data.keys())
    else:
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = f'./net_res_{current_time}.json'
        print(f"json_path: {json_path}")

    if args.rpk:
        models = args.rpk
    else:
        models = [os.path.join(args.rpk_folder, file_name)
                  for file_name in os.listdir(args.rpk_folder)
                  if file_name.endswith(".rpk")]

    if args.postprocess:
        print("Warning: --postprocess mode is unstable.\n\t"
              "- Code may break.\n\t"
              "- Results can vary significantly between runs.")

    for model_path in models:
        if extract_name(model_path) in skip_models_names:
            print(f"skip model: {model_path}")
            continue
        p = multiprocessing.Process(target=run_model, args=(model_path,))
        p.start()
        p.join()
        print(f"Completed testing for model: {model_path}")
    print("Finished")
