# Model zoo

The `imx500_classification_demo.py` application is an example for the classification task and includes the following arguments:

- "--model", type=str, help="Path of the model"
- "--softmax" action="store_true", help="Add post-process softmax"
- "-r", "--preserve-aspect-ratio" action="store_true", help="preprocess the image with preserve aspect ratio"
- "--labels", type=str, default="assets/imagenet_labels.txt", help="Path to the labels file"

The `imx500_instance_segmentation_demo.py` application is an example for the instance segmentation task and includes the following arguments:

- "--model", type=str, required=True, help="Path of the model"
- "--score-threshold", type=float, default=0.1, help="Detection threshold"
- "--mask-threshold", type=float, default=0.5, help="Mask threshold"
- "--iou-threshold", type=float, default=0.7, help="IoU (Intersection over Union) threshold for Non-Maximum Suppression (NMS)"
- "--max-out-dets", type=int, default=5, help="Maximum number of output detections to keep after NMS"
- "--labels", type=str, default="assets/coco_labels.txt", help="Path to the labels file"


The `imx500_object_detection_demo.py` application is an example for the object detection task and includes the following arguments:

- "--model", type=str, required=True, help="Path of the model"
- "--bbox-normalization", action="store_true", help="Normalize bbox"
- "--threshold", type=float, default=0.55, help="Detection threshold"
- "--iou", type=float, default=0.65, help="Set iou threshold"
- "--max-detections", type=int, default=10, help="Set max detections"
- "--ignore-dash-labels", action="store_true", help="Remove '-' labels"
- "-r", "--preserve-aspect-ratio" action="store_true", help="preprocess the image with preserve aspect ratio"
- "--labels", type=str, default="assets/coco_labels.txt", help="Path to the labels file"

The `imx500_pose_estimation.py` application is an example for the pose estimation task and includes the following arguments:

- "--model", type=str, required=True, help="Path of the model"
- "--box-min-confidence", type=float, default=0.3, help="Confidence threshold for bounding box predictions"
- "--keypoint-min-confidence", type=float, default=0.3, help="Minimum confidence required for keypoints"
- "--iou-threshold", type=float, default=0.7, help="IoU (Intersection over Union) threshold for Non-Maximum Suppression (NMS)"
- "--max-out-dets", type=int, default=300, help="Maximum number of output detections to keep after NMS"
- "--labels", type=str, default="assets/coco_labels.txt", help="Path to the labels file"

The `imx500_segmentation_demo.py` application is an example for the segmentation task and uses the deeplabv3plus model.

In the table below you can find information regarding all models in the model zoo.

| model                              | task                  | input size | script call                                                                                                                                         |
|------------------------------------|-----------------------|------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| efficientnet_bo                    | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnet_bo.rpk --softmax                                         |
| efficientnet_lite0                 | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnet_lite0.rpk --softmax                                      |
| efficientnetv2_b0                  | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b0.rpk --preserve-aspect-ratio                         |
| efficientnetv2_b1                  | classification        | 240x240    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b1.rpk --preserve-aspect-ratio                         |
| efficientnetv2_b2                  | classification        | 260x260    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b2.rpk --preserve-aspect-ratio                         |
| levit_128s                         | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_levit_128s.rpk --preserve-aspect-ratio                                |
| mnasnet1.0                         | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mnasnet1.0.rpk --softmax                                              |
| mobilenet_v2                       | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilenet_v2.rpk --preserve-aspect-ratio                              |
| mobilevit_xs                       | classification        | 256x256    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilevit_xs.rpk --softmax --preserve-aspect-ratio                    |
| mobilevit_xxs                      | classification        | 256x256    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilevit_xxs.rpk --softmax --preserve-aspect-ratio                   |
| regnetx_002                        | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnetx_002.rpk --softmax                                             |
| regnety_002                        | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnety_002.rpk --softmax                                             |
| regnety_004                        | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnety_004.rpk --softmax                                             |
| resnet18                           | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_resnet18.rpk --softmax                                                |
| shufflenet_v2_x1_5                 | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_shufflenet_v2_x1_5.rpk                                                |
| squeezenet1.0                      | classification        | 224x224    | imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_squeezenet1.0.rpk                                                     |  
| efficientdet_lite0                 | object detection      | 320x320    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_efficientdet_lite0.rpk --postprocess efficientdet_lite0             |
| efficientdet_lite0_pp              | object detection      | 320x320    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_efficientdet_lite0_pp.rpk --bbox-normalization -r                   |
| nanodet_plus_416x416               | object detection      | 416x416    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_nanodet_plus_416x416.rpk --ignore-dash-labels --postprocess nanodet |
| nanodet_plus_416x416_pp            | object detection      | 416x416    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_nanodet_plus_416x416_pp.rpk --ignore-dash-labels                    |
| ssd_mobilenetv2_fpnlite_320x320_pp | object detection      | 320x320    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.rpk                              |
| yolov5n                            | object detection      | 640x640    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_yolov5n.rpk --postprocess yolov5n -r                                |
| yolov8n                            | object detection      | 640x640    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_yolov8n.rpk --ignore-dash-labels --postprocess yolov8n -r           |
| yolov8n_pp                         | object detection      | 640x640    | imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_yolov8n_pp.rpk --ignore-dash-labels -r                              |
| deeplabv3plus                      | segmentation          | 320x320    | imx500_segmentation_demo.py  --model /usr/share/imx500-models/imx500_network_deeplabv3plus.rpk                                                      |
| yolov8n_inst_seg                   | instance segmentation | 640x640    | imx500_instance_segmentation_demo.py --model /usr/share/imx500-models/imx500_network_yolov8n_inst_seg.rpk                                           |
| higherhrnet_coco                   | pose estimation       | 228x640    | imx500_pose_estimation_higherhrnet_demo.py --model /usr/share/imx500-models/imx500_network_higherhrnet_coco.rpk                                     |
| yolov8n-pos                        | pose estimation       | 640x640    | imx500_pose_estimation_yolov8n_demo.py --model /usr/share/imx500-models/imx500_network_yolov8n_pose.rpk                                             |