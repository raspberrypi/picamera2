"""
convert json outputs of fps_auto.py to csv - only when using mode ["search", "only_output"]
not supporting mode "all"
"""
import argparse
import json
import pandas as pd

sort_order = [
    "efficientnet_bo",
    "efficientnet_lite0",
    "efficientnetv2_b0",
    "efficientnetv2_b1",
    "efficientnetv2_b2",
    "levit_128s",
    "mnasnet1.0",
    "mobilenet_v2",
    "mobilevit_xs",
    "mobilevit_xxs",
    "regnetx_002",
    "regnety_002",
    "regnety_004",
    "resnet18",
    "shufflenet_v2_x1_5",
    "squeezenet1.0",
    "yolov8n_inst_seg",
    "higherhrnet_coco",
    "yolov8n_pose",
    "efficientdet_lite0",
    "efficientdet_lite0_pp",
    "nanodet_plus_416x416",
    "nanodet_plus_416x416_pp",
    "ssd_mobilenetv2_fpnlite_320x320_pp",
    "yolov5n",
    "yolov8n",
    "yolov8n_pp",
    "deeplabv3plus"
]


def custom_round(val):
    val = float(val)
    if val % 1 < 0.2:
        return int(val)
    elif val % 1 >= 0.8:
        return round(val)
    else:
        return round(val, 2)


def run(json_path):
    with open(json_path) as file:
        data = json.load(file)
    data_list = []
    for model_name, value in data.items():
        assert len(value) == 1, "did you send all mode?"
        v = value[list(value.keys())[0]]
        user_fps = v['user_fps']
        dnn_runtime = round(float(v['dnn_runtime']), 2) if v['dnn_runtime'] != "NA" else "NA"
        dsp_runtime = round(float(v['dsp_runtime']), 2) if v['dsp_runtime'] != "NA" else "NA"
        fps = custom_round(v['fps'])
        dps = custom_round(v['dps'])
        loading_output = v['loading_output']
        total_postprocess_time = v.get('total_postprocess_time', "NA")
        data_list.append([model_name, user_fps, dnn_runtime, dsp_runtime, fps, dps, loading_output, total_postprocess_time])
    # Create the DataFrame
    df = pd.DataFrame(data_list, columns=["model_zoo_name", "max user fps", "dnn ms", "dsp ms", "fps", "dps",
                                          "loading_output", "total_postprocess_time"])
    # Sort the DataFrame according to the custom sort order
    df['sort_key'] = df['model_zoo_name'].apply(lambda x: sort_order.index(x) if x in sort_order else len(sort_order))
    df = df.sort_values(by='sort_key').drop(columns=['sort_key'])
    csv_path = json_path.replace(".json", ".csv")
    df.to_csv(csv_path, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_path", required=True, type=str, help="path to json file")
    args = parser.parse_args()
    run(args.json_path)
