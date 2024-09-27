"""
Highernet postprocessing

This code is based on multiple sources:
https://github.com/HRNet/HigherHRNet-Human-Pose-Estimation
https://github.com/princeton-vl/pose-ae-train
https://github.com/yinguobing/facial-landmark-detection-hrnet
"""

from typing import Tuple

import cv2
import numpy as np

try:
    from munkres import Munkres
except ImportError:
    raise ImportError("Please install munkres first. `pip3 install --break-system-packages munkres`")

default_joint_order = [0, 1, 2, 3, 4, 5, 6, 11, 12, 7, 8, 9, 10, 13, 14, 15, 16]


def postprocess_higherhrnet(outputs: list[np.ndarray, np.ndarray],
                            img_size,
                            img_w_pad,
                            img_h_pad,
                            network_postprocess,
                            num_joints=17,
                            tag_per_joint=True,
                            joint_order=default_joint_order,
                            detection_threshold=0.3,
                            max_num_people=30,
                            nms_kernel=5,
                            nms_padding=2,
                            ignore_too_much=False,
                            use_detection_val=True,
                            tag_threshold=1.0,
                            adjust=False,
                            refine=False,
                            input_image_size=(288, 384),
                            output_shape=(144, 192)) -> Tuple[list[list], list, list[list]]:
    all_preds = []
    all_scores = []
    if network_postprocess:
        # outputs [[B, max_num_people, num_joints], [B, max_num_people, num_joints], [B, max_num_people, num_joints]]
        grouped, scores = parse(network_outputs=[outputs[0][0, ...],
                                                 outputs[1][0, ...],
                                                 outputs[2][0, ...]],
                                output_shape=output_shape,
                                adjust=adjust,
                                refine=refine,
                                network_postprocess=network_postprocess,
                                tag_per_joint=tag_per_joint,
                                max_num_people=max_num_people,
                                nms_kernel=nms_kernel,
                                nms_padding=nms_padding,
                                num_joints=num_joints,
                                joint_order=joint_order,
                                detection_threshold=detection_threshold,
                                ignore_too_much=ignore_too_much,
                                use_detection_val=use_detection_val,
                                tag_threshold=tag_threshold)
    else:
        out0 = outputs[0][0]
        out1 = outputs[1][0]

        # postprocess:
        # resize first output to 2nd output size
        out0 = ResizeBilinear(out0, out1.shape[0], out1.shape[1])
        # average heatmaps from both outputs
        heatmaps = (out0[..., :17] + out1) / 2
        tags = out0[..., 17:]
        grouped, scores = parse(network_outputs=[heatmaps, tags],
                                output_shape=output_shape,
                                adjust=adjust,
                                refine=refine,
                                network_postprocess=network_postprocess,
                                tag_per_joint=tag_per_joint,
                                max_num_people=max_num_people,
                                nms_kernel=nms_kernel,
                                nms_padding=nms_padding,
                                num_joints=num_joints,
                                joint_order=joint_order,
                                detection_threshold=detection_threshold,
                                ignore_too_much=ignore_too_much,
                                use_detection_val=use_detection_val,
                                tag_threshold=tag_threshold)

    # scale keypoints coordinates to input image size
    scale_factor = (np.array(input_image_size) / output_shape).reshape((1, 1, 2))
    for img_index in range(len(grouped)):
        if grouped[img_index].shape[0] > 0:
            # rescale to preprocessed input image size
            grouped[img_index][:, :, :2] = grouped[img_index][:, :, :2] * scale_factor
            # remove pad offset:
            grouped[img_index][:, :, 0] = grouped[img_index][:, :, 0] - img_w_pad[0]
            grouped[img_index][:, :, 1] = grouped[img_index][:, :, 1] - img_h_pad[0]
            # rescale to original image size
            resized_input_image = np.array(input_image_size) - np.array(
                (sum(img_h_pad),
                 sum(img_w_pad)))
            s = (np.array(img_size) / resized_input_image).reshape((1, 1, 2))
            grouped[img_index][:, :, :2] = grouped[img_index][:, :, :2] * s

    # Calculate zero keypoint
    zero_kpt = np.zeros((1, 4))
    resized_input_image = np.array(input_image_size) - np.array(
        (sum(img_h_pad),
         sum(img_w_pad)))
    s = (np.array(img_size) / resized_input_image).reshape((1, 1, 2))
    zero_kpt[:, 0] = zero_kpt[:, 0] - img_w_pad[0]
    zero_kpt[:, 1] = zero_kpt[:, 1] - img_h_pad[0]
    zero_kpt[:, :2] = zero_kpt[:, :2] * s

    all_preds.append(grouped)
    all_scores.append(scores)

    kpts = []
    # one image, one iter
    for idx, _kpts in enumerate(all_preds):
        for idx_kpt, kpt in enumerate(_kpts[0]):
            area = (np.max(kpt[:, 0]) - np.min(kpt[:, 0])) * (np.max(kpt[:, 1]) - np.min(kpt[:, 1]))
            # kpt [17, 4]
            kpt = processKeypoints(kpt)
            kpts.append(
                {
                    'keypoints': kpt[:, 0:3],
                    'score': all_scores[idx][idx_kpt],
                    'tags': kpt[:, 3],
                    'area': area
                }
            )
    # _coco_keypoint_results_one_category_kernel
    out_keypoints = []
    out_scores = []
    out_bbox = []

    # for img_kpts in kpts:
    img_kpts = kpts
    if len(img_kpts) == 0:
        return [], [], []

    _key_points = np.array(
        [img_kpts[k]['keypoints'] for k in range(len(img_kpts))]
    )
    key_points = np.zeros(
        (_key_points.shape[0], num_joints * 3),
        dtype=np.float32
    )

    for ipt in range(num_joints):
        key_points[:, ipt * 3 + 0] = _key_points[:, ipt, 0]
        key_points[:, ipt * 3 + 1] = _key_points[:, ipt, 1]
        key_points[:, ipt * 3 + 2] = _key_points[:, ipt, 2]  # keypoints score.

    for k in range(len(img_kpts)):
        kpt = key_points[k].reshape((num_joints, 3))
        # ignore zero kpts
        mask = np.isin(kpt, zero_kpt)
        kpt = np.where(mask, np.nan, kpt)
        left_top = np.nanmin(kpt, axis=0)
        right_bottom = np.nanmax(kpt, axis=0)

        out_keypoints.append(list(key_points[k]))
        out_scores.append(img_kpts[k]['score'])
        out_bbox.append([left_top[1], left_top[0], right_bottom[1], right_bottom[0]])
    return out_keypoints, out_scores, out_bbox


def parse(network_outputs,
          output_shape,
          adjust=False,
          refine=False,
          network_postprocess=False,
          tag_per_joint=17,
          max_num_people=30,
          nms_kernel=5,
          nms_padding=2,
          num_joints=17,
          joint_order=default_joint_order,
          detection_threshold=0.1,
          ignore_too_much=False,
          use_detection_val=True,
          tag_threshold=1.0
          ):
    if network_postprocess:
        tag_k, ind_k, val_k = network_outputs
        x = ind_k % output_shape[1]
        y = (ind_k / output_shape[1]).astype(ind_k.dtype)
        ind_k = np.stack([x, y], axis=2)

        topk_output_dict = {'tag_k': tag_k[np.newaxis, ...],
                            'loc_k': ind_k[np.newaxis, ...],
                            'val_k': val_k[np.newaxis, ...],
                            }
    else:
        det, tag = network_outputs
        # topk_output_dict
        # {'tag_k': [num_images, max_num_people, num_joints],
        # 'loc_k': [num_images, max_num_people, num_joints, 2],
        # 'val_k': [num_images, max_num_people, num_joints]}
        topk_output_dict = top_k(det=det,
                                 tag=tag,
                                 tag_per_joint=tag_per_joint,
                                 max_num_people=max_num_people,
                                 nms_kernel=nms_kernel,
                                 nms_padding=nms_padding)
    # ans [num_joints_detected, num_joints, 4]
    ans = match(tag_k=topk_output_dict['tag_k'],
                loc_k=topk_output_dict['loc_k'],
                val_k=topk_output_dict['val_k'],
                num_joints=num_joints,
                joint_order=joint_order,
                detection_threshold=detection_threshold,
                max_num_people=max_num_people,
                ignore_too_much=ignore_too_much,
                use_detection_val=use_detection_val,
                tag_threshold=tag_threshold)
    if adjust:
        # ans [[num_joints_detected, num_joints, 4]]
        ans = adjust_func(ans, det[np.newaxis, ...])  # TODO support batch size > 1

    scores = [i[:, 2].mean() for i in ans[0]]

    if refine:
        ans = ans[0]
        # for every detected person
        for _ in range(len(ans)):
            # NotImplemented
            if not tag_per_joint:
                raise NotImplementedError

        # ans [[num_joints_detected, num_joints, 4]]
        ans = [ans]
    return ans, scores


def ResizeBilinear(img, new_height, new_width):
    return cv2.resize(img, (new_width, new_height))


def top_k(det,
          tag,
          tag_per_joint=17,
          max_num_people=30,
          nms_kernel=5,
          nms_padding=2):
    # det [144, 192, 17]
    # tag [144, 192, 17]

    # det [144, 192, 17]
    det = nms(det,
              nms_kernel=nms_kernel,
              nms_padding=nms_padding)
    # num_images 1
    # h 144
    # w 192
    # num_joints 17
    num_images, h, w, num_joints = (1,) + det.shape  # TODO: support multiple images (batch>1)

    # det [num_images, h*w, num_joints]
    det = det.reshape((num_images, -1, num_joints))
    # val_k [num_images, max_num_people, num_joints]
    val_k, ind = np_topk(det, max_num_people)

    # tag [num_images, h*w, num_joints]
    tag = tag.reshape((num_images, -1, num_joints))

    # NotImplemented
    if not tag_per_joint:
        raise NotImplementedError
        tag = tag.expand(-1, num_joints, -1, -1)

    # tag_k [num_images, max_num_people, num_joints]
    tag_k = np.zeros((num_images, max_num_people, num_joints))
    for img in range(num_images):
        for kp in range(num_joints):
            tag_k[img, :, kp] = tag[img, ind[img, :, kp], kp]

    x = ind % w
    y = (ind / w).astype(ind.dtype)

    # ind_k [num_images, max_num_people, num_joints, 2]
    ind_k = np.stack([x, y], axis=3)

    # {'tag_k': [num_images, max_num_people, num_joints],
    # 'loc_k': [num_images, max_num_people, num_joints, 2],
    # 'val_k': [num_images, max_num_people, num_joints]}
    return {'tag_k': tag_k,
            'loc_k': ind_k,
            'val_k': val_k,
            }


def nms(det,
        nms_kernel=5,
        nms_padding=2):
    # det [144, 192, 17]
    # maxm [144, 192, 17]
    maxm = np_max_pool(det, k=nms_kernel, p=nms_padding)
    maxm = np.equal(maxm, det).astype(np.float32)
    det = det * maxm
    return det


def np_max_pool(x,
                k=5,
                p=2,
                p_value=0):
    # x [144, 192, 17]
    # k - kernel size (h, w)
    # p - padding size (top, bottom, left, right)
    if isinstance(k, int):
        k = (k, k)
    if isinstance(p, int):
        p = ((p, p), (p, p), (0, 0))
    elif isinstance(p, (list, tuple)) and len(p) == 2:
        p = ((p[0], p[0]), (p[1], p[1]), (0, 0))

    # y [148, 196, 17
    y = np.pad(x, p)
    out = np.concatenate(
        [np.max(np.concatenate([y[ky:ky + y.shape[0] - k[0] + 1, kx:kx + y.shape[1] - k[1] + 1, c:c + 1]
                                for ky in range(k[0])
                                for kx in range(k[1])], 2), axis=2, keepdims=True) for c in range(y.shape[2])], 2)
    # out [144, 192, 17]
    return out


def np_topk(x, k):
    # x [1, 27648, 17]
    # n_images 1
    # n_keypoints 17
    n_images, _, n_keypoints = x.shape
    # vals [1, k, 17]
    # inds [1, k, 17]
    vals = np.zeros((n_images, k, n_keypoints), dtype=x.dtype)
    inds = np.zeros((n_images, k, n_keypoints), dtype=np.int64)
    for img in range(n_images):
        for kp in range(n_keypoints):
            # _inds [k]
            _inds = np.argpartition(x[img, :, kp], -k)[-k:]
            _inds = _inds[np.argsort(x[img, _inds, kp], )][::-1]
            inds[img, :, kp] = _inds
            vals[img, :, kp] = x[img, _inds, kp]
    return vals, inds


def match(tag_k,
          loc_k,
          val_k,
          num_joints=17,
          joint_order=default_joint_order,
          detection_threshold=0.1,
          max_num_people=30,
          ignore_too_much=False,
          use_detection_val=True,
          tag_threshold=1.0):
    def m(x):
        return match_by_tag(inp=x,
                            num_joints=num_joints,
                            joint_order=joint_order,
                            detection_threshold=detection_threshold,
                            max_num_people=max_num_people,
                            ignore_too_much=ignore_too_much,
                            use_detection_val=use_detection_val,
                            tag_threshold=tag_threshold)
    return list(map(m, zip(tag_k, loc_k, val_k)))


def match_by_tag(inp,
                 num_joints=17,
                 joint_order=default_joint_order,
                 detection_threshold=0.1,
                 max_num_people=30,
                 ignore_too_much=False,
                 use_detection_val=True,
                 tag_threshold=1.0):
    # tag_k [num_images, max_num_people, num_joints]
    # loc_k [num_images, max_num_people, num_joints, 2]
    # val_k [num_images, max_num_people, num_joints]
    tag_k, loc_k, val_k = inp
    # default_ [num_joints, 4]
    default_ = np.zeros((num_joints, 3 + 1))  # tag_k.shape[2] assumed to be 1  # pytorch shape: (17, 4)

    joint_dict = {}
    tag_dict = {}
    for i in range(num_joints):
        idx = joint_order[i]

        # tags [max_num_people, 1]
        tags = tag_k[:, idx:idx + 1]
        # joints [max_num_people, 4]
        joints = np.concatenate((loc_k[:, idx, :], val_k[:, idx:idx + 1], tags), 1)
        # mask [max_num_people]
        mask = joints[:, 2] > detection_threshold
        tags = tags[mask]
        joints = joints[mask]

        if joints.shape[0] == 0:
            continue

        if i == 0 or len(joint_dict) == 0:
            for tag, joint in zip(tags, joints):
                key = tag[0]
                joint_dict.setdefault(key, np.copy(default_))[idx] = joint
                tag_dict[key] = [tag]
        else:
            grouped_keys = list(joint_dict.keys())[:max_num_people]
            grouped_tags = [np.mean(tag_dict[i], axis=0) for i in grouped_keys]

            if ignore_too_much \
                    and len(grouped_keys) == max_num_people:
                continue

            diff = joints[:, None, 3:] - np.array(grouped_tags)[None, :, :]
            diff_normed = np.linalg.norm(diff, ord=2, axis=2)
            diff_saved = np.copy(diff_normed)

            if use_detection_val:
                diff_normed = np.round(diff_normed) * 100 - joints[:, 2:3]

            num_added = diff.shape[0]
            num_grouped = diff.shape[1]

            if num_added > num_grouped:
                diff_normed = np.concatenate(
                    (
                        diff_normed,
                        np.zeros((num_added, num_added - num_grouped)) + 1e10
                    ),
                    axis=1
                )

            pairs = py_max_match(diff_normed)
            for row, col in pairs:
                if (
                        row < num_added
                        and col < num_grouped
                        and diff_saved[row][col] < tag_threshold
                ):
                    key = grouped_keys[col]
                    joint_dict[key][idx] = joints[row]
                    tag_dict[key].append(tags[row])
                else:
                    key = tags[row][0]
                    joint_dict.setdefault(key, np.copy(default_))[idx] = \
                        joints[row]
                    tag_dict[key] = [tags[row]]

    # ans [len(joint_dict), num_joints, 4]
    ans = np.array([joint_dict[i] for i in joint_dict]).astype(np.float32)
    return ans


def py_max_match(scores):
    m = Munkres()
    tmp = m.compute(scores)
    tmp = np.array(tmp).astype(np.int32)
    return tmp


def adjust_func(ans, det):
    # ans [[num_joints_detected, num_joints, 4]]
    # det [144, 192, 17]
    for batch_id, people in enumerate(ans):
        for people_id, i in enumerate(people):
            for joint_id, joint in enumerate(i):
                if joint[2] > 0:
                    y, x = joint[0:2]
                    xx, yy = int(x), int(y)
                    # print(batch_id, joint_id, det[batch_id].shape)
                    tmp = det[batch_id][..., joint_id]
                    if tmp[xx, min(yy + 1, tmp.shape[1] - 1)] > tmp[xx, max(yy - 1, 0)]:
                        y += 0.25
                    else:
                        y -= 0.25

                    if tmp[min(xx + 1, tmp.shape[0] - 1), yy] > tmp[max(0, xx - 1), yy]:
                        x += 0.25
                    else:
                        x -= 0.25
                    ans[batch_id][people_id, joint_id, 0:2] = (y + 0.5, x + 0.5)
    # ans [[num_joints_detected, num_joints, 4]]
    return ans


def refine_func(det, tag, keypoints):
    # det [144, 192, 17]
    # tag [144, 192, 17]
    # keypoints [num_joints, 4]
    if len(tag.shape) == 3:
        # tag shape: (17, 128, 128, 1)
        # tag [144, 192, 17, 1]
        tag = tag[:, :, :, None]

    tags = []
    for i in range(keypoints.shape[0]):
        if keypoints[i, 2] > 0:
            # save tag value of detected keypoint
            x, y = keypoints[i][:2].astype(np.int32)
            tags.append(tag[y, x, i])

    # mean tag of current detected people
    prev_tag = np.mean(tags, axis=0)
    ans = []

    for i in range(keypoints.shape[0]):
        # score of joints i at all position
        tmp = det[:, :, i]
        # distance of all tag values with mean tag of current detected people
        tt = (((tag[:, :, i] - prev_tag[None, None, :]) ** 2).sum(axis=2) ** 0.5)
        tmp2 = tmp - np.round(tt)

        # find maximum position
        y, x = np.unravel_index(np.argmax(tmp2), tmp.shape)
        xx = x
        yy = y
        # detection score at maximum position
        val = tmp[y, x]
        # offset by 0.5
        x += 0.5
        y += 0.5

        # add a quarter offset
        if tmp[yy, min(xx + 1, tmp.shape[1] - 1)] > tmp[yy, max(xx - 1, 0)]:
            x += 0.25
        else:
            x -= 0.25

        if tmp[min(yy + 1, tmp.shape[0] - 1), xx] > tmp[max(0, yy - 1), xx]:
            y += 0.25
        else:
            y -= 0.25

        ans.append((x, y, val))
    ans = np.array(ans)

    if ans is not None:
        for i in range(det.shape[2]):
            # add keypoint if it is not detected
            if ans[i, 2] > 0 and keypoints[i, 2] == 0:
                # if ans[i, 2] > 0.01 and keypoints[i, 2] == 0:
                keypoints[i, :2] = ans[i, :2]
                keypoints[i, 2] = ans[i, 2]
    # keypoints [num_joints_detected, num_joints, 4]
    return keypoints


def processKeypoints(keypoints):
    # keypoints [17, 4]
    tmp = keypoints.copy()
    if keypoints[:, 2].max() > 0:
        num_keypoints = keypoints.shape[0]
        for i in range(num_keypoints):
            tmp[i][0:3] = [
                float(keypoints[i][0]),
                float(keypoints[i][1]),
                float(keypoints[i][2])
            ]

    return tmp
