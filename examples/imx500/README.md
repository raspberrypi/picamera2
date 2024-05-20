# Model zoo

The `imx500_classification_demo.py` application is an example for the classification task and includes the following arguments:

- "--model", type=str, help="Path of the model"

The `imx500_object_detection_demo.py` application is an example for the object detection task and includes the following arguments:

- "--model", type=str, help="Path of the model"
- "--bbox-normalization", action="store_true", help="Normalize bbox"
- "--swap-tensors", action="store_true", help="Swap tensor 1 and 2"
- "--threshold", type=float, default=0.55, help="Detection threshold"

The `imx500_segmentation_demo.py` application is an example for the segmentation task and uses the deeplabv3plus model.


In the table below you can find information regarding all models in the model zoo.

| model                              | task                 |input size | script call              |
|------------------------------------|----------------------|-----------|--------------------------|
| efficientnet_lite0                 | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_efficientnet_lite0.fpk
| efficientnetv2_b0                  | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_efficientnetv2_b0.fpk
| efficientnetv2_b1                  | classification       | 240x240   | imx500_classification_demo.py --model networks/imx500_network_efficientnetv2_b1.fpk
| efficientnetv2_b2                  | classification       | 260x260   | imx500_classification_demo.py --model networks/imx500_network_efficientnetv2_b2.fpk
| efficientnet_bo                    | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_efficientnet_bo.fpk
| resnet18                           | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_resnet18.fpk
| regnety_002                        | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_regnety_002.fpk
| regnetx_002                        | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_regnetx_002.fpk
| regnety_004                        | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_regnety_004.fpk
| mobilevit_xs                       | classification       | 256x256   | imx500_classification_demo.py --model networks/imx500_network_mobilevit_xs.fpk
| mobilevit_xxs                      | classification       | 256x256   | imx500_classification_demo.py --model networks/imx500_network_mobilevit_xxs.fpk
| levit_128s                         | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_levit_128s.fpk
| mobilenet_v2                       | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_mobilenet_v2.fpk
| shufflenet_v2_x1_5                 | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_shufflenet_v2_x1_5.fpk
| mnasnet1.0                         | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_mnasnet1.0.fpk
| squeezenet1.0                      | classification       | 224x224   | imx500_classification_demo.py --model networks/imx500_network_squeezenet1.0.fpk
| ssd_mobilenetv2_fpnlite_320x320_pp | object detection     | 320x320   | imx500_object_detection_demo.py --model networks/imx500_network_ssd_mobilenetv2_fpnlite_320x320_pp.fpk
| nanodet_plus_416x416_pp            | object detection     | 416x416   | imx500_object_detection_demo.py --model networks/imx500_network_nanodet_plus_416x416_pp.fpk --ignore-dash-labels
| efficientdet_lite0_pp              | object detection     | 320x320   | imx500_object_detection_demo.py --model networks/imx500_network_efficientdet_lite0_pp.fpk --bbox-normalization
| yolov8n_pp                         | object detection     | 640x640   | imx500_object_detection_demo.py --model networks/imx500_network_yolov8n_pp.fpk --ignore-dash-labels
| deeplabv3plus                      | segmentation         | 320x320   | imx500_segmentation_demo.py
