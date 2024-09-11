# Model zoo

## Example files
| Application Name                             | Task                  |
|----------------------------------------------|-----------------------|
| `imx500_classification_demo.py`              | Classification        |
| `imx500_object_detection_demo.py`            | Object Detection      |
| `imx500_segmentation_demo.py`                | Segmentation          |

## Models
| model                      | task             | input size | Color Format | script call                                                                                                                                         |
|----------------------------|------------------|------------|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| efficientnet_b0            | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnet_b0.rpk --softmax`                                |
| efficientnet_lite0         | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnet_lite0.rpk --softmax`                             |
| efficientnetv2_b0          | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b0.rpk --preserve-aspect-ratio`                |
| efficientnetv2_b1          | classification   | 240x240    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b1.rpk --preserve-aspect-ratio --fps 29`       |
| efficientnetv2_b2          | classification   | 260x260    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_efficientnetv2_b2.rpk --preserve-aspect-ratio --fps 26`       |
| levit_128s                 | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_levit_128s.rpk --preserve-aspect-ratio`                       |
| mnasnet1.0                 | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mnasnet1.0.rpk --softmax`                                     |
| mobilenet_v2               | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilenet_v2.rpk --preserve-aspect-ratio`                     |
| mobilevit_xs               | classification   | 256x256    | GBR          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilevit_xs.rpk --softmax --preserve-aspect-ratio --fps 22`  |
| mobilevit_xxs              | classification   | 256x256    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_mobilevit_xxs.rpk --softmax --preserve-aspect-ratio --fps 26` |
| regnetx_002                | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnetx_002.rpk --softmax`                                    |
| regnety_002                | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnety_002.rpk --softmax`                                    |
| regnety_004                | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_regnety_004.rpk --softmax`                                    |
| resnet18                   | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_resnet18.rpk --softmax --fps 29`                              |
| shufflenet_v2_x1_5         | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_shufflenet_v2_x1_5.rpk`                                       |
| squeezenet1.0              | classification   | 224x224    | RGB          | `python imx500_classification_demo.py --model /usr/share/imx500-models/imx500_network_squeezenet1.0.rpk`                                            |
| efficientdet_lite0_pp      | object detection | 320x320    | RGB          | `python imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_efficientdet_lite0_pp.rpk --bbox-normalization -r --fps 23` |
| nanodet_plus_416x416_pp    | object detection | 416x416    | GBR          | `python imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_nanodet_plus_416x416_pp.rpk --ignore-dash-labels --fps 23`  |
| ssd_mobilenetv2_fpnlite_pp | object detection | 320x320    | RGB          | `python imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_ssd_mobilenetv2_fpnlite_pp.rpk --fps 26`                    |
| yolov8n_pp                 | object detection | 640x640    | RGB          | `python imx500_object_detection_demo.py --model /usr/share/imx500-models/imx500_network_yolov8n_pp.rpk --ignore-dash-labels -r --fps 16`            |
| deeplabv3plus              | segmentation     | 320x320    | RGB          | `python imx500_segmentation_demo.py  --model /usr/share/imx500-models/imx500_network_deeplabv3plus.rpk --fps 19`                                    |