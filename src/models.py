from configobj import ConfigObj
from time import time

import numpy as np
from scipy.ndimage.filters import gaussian_filter

from tensorflow import keras as tfk
import cv2
tfkl = tfk.layers
tfkb = tfk.backend


class CPM:
    def __init__(self, input_shape=(None, None, 3), dropout_rate=0.1, n_parts=16):
        self.input_shape = input_shape
        self.dropout_rate = dropout_rate
        self.n_parts = n_parts

    def create_model(self):
        input_image = tfk.Input(shape=self.input_shape)

        features = self._feature_extractor(input_image)
        first_stage_believes = self._cpm_first_stage(input_image)

        second_stage_believes = self._cpm_second_stage(features, first_stage_believes, prefix='stage2_')

        third_stage_believes = self._cpm_second_stage(features, second_stage_believes, prefix='stage3_')

        fourth_stage_believes = self._cpm_second_stage(features, third_stage_believes, prefix='stage4_')

        out = tfkl.Activation('sigmoid', name='final_heatmaps')(fourth_stage_believes)

        model = tfk.Model(input_image, out)
        return model

    def _cpm_first_stage(self, input_image):
        y = self._conv2d(input_image, filters=16, kernel_size=(3, 3))
        y = self._conv2d(y, filters=16, kernel_size=(3, 3))
        x = self._add_skip_connection(input_image, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=32, kernel_size=(3, 3))
        y = self._conv2d(y, filters=32, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=64, kernel_size=(3, 3))
        y = self._conv2d(y, filters=64, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=128, kernel_size=(2, 2))
        y = self._conv2d(y, filters=128, kernel_size=(2, 2))
        x = self._add_skip_connection(x, y)

        y = self._conv2d(x, filters=256, kernel_size=(3, 3))
        y = self._conv2d(y, filters=256, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)

        x = self._conv2d(x, 64, kernel_size=(1, 1))

        out = tfkl.Conv2D(self.n_parts, (1, 1), padding='same', activation=None, name='stage1_repr')(x)
        out = tfkl.BatchNormalization()(out)
        out = tfkl.Activation('relu')(out)
        out = tfkl.SpatialDropout2D(self.dropout_rate)(out)
        return out

    def _cpm_second_stage(self, extracted_features, former_believes, prefix):
        input_tensor = tfkl.concatenate([extracted_features, former_believes],
                                        axis=-1, name=prefix + 'concat')

        y = self._conv2d(input_tensor, filters=64, kernel_size=(4, 4))
        y = self._conv2d(y, filters=64, kernel_size=(4, 4))
        x = self._add_skip_connection(input_tensor, y)

        y = self._conv2d(x, filters=128, kernel_size=(4, 4))
        y = self._conv2d(y, filters=128, kernel_size=(4, 4))
        x = self._add_skip_connection(x, y)

        y = self._conv2d(x, filters=256, kernel_size=(3, 3))
        y = self._conv2d(y, filters=256, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)

        x = self._conv2d(x, 64, kernel_size=(1, 1))
        out = tfkl.Conv2D(self.n_parts, (1, 1), padding='same', name=prefix + 'repr')(x)
        return out

    def _feature_extractor(self, input_image):
        y = self._conv2d(input_image, filters=16, kernel_size=(3, 3))
        y = self._conv2d(y, filters=16, kernel_size=(3, 3))
        x = self._add_skip_connection(input_image, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=32, kernel_size=(3, 3))
        y = self._conv2d(y, filters=32, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=64, kernel_size=(3, 3))
        y = self._conv2d(y, filters=64, kernel_size=(3, 3))
        x = self._add_skip_connection(x, y)
        x = tfkl.MaxPooling2D(2, strides=2, padding='same')(x)

        y = self._conv2d(x, filters=128, kernel_size=(2, 2))
        y = self._conv2d(y, filters=128, kernel_size=(2, 2))
        x = self._add_skip_connection(x, y)

        x = tfkl.Conv2D(self.n_parts, (1, 1), padding='same')(x)
        return x

    def _conv2d(self, x, filters, kernel_size):
        out = tfkl.Conv2D(filters, kernel_size, padding='same')(x)
        out = tfkl.BatchNormalization()(out)
        out = tfkl.Activation('relu')(out)
        out = tfkl.SpatialDropout2D(self.dropout_rate)(out)
        return out

    def _add_skip_connection(self, x, y, scale_factor=0.5):
        channels = tfkb.int_shape(y)[-1]
        shortcut_branch = tfkl.Conv2D(filters=channels, kernel_size=(1, 1), padding='same')(x)
        out = self._weighted_add(shortcut_branch, y, scale_factor)
        return tfkl.Activation('relu')(out)

    @staticmethod
    def _weighted_add(shortcut_branch, inception_branch, scale_factor):
        return tfkl.Lambda(lambda inputs, scale: inputs[0] + inputs[1] * scale,
                           arguments={'scale': scale_factor})([shortcut_branch, inception_branch])


class StackedHurglassNetwork:
    pass


class OpenPose:
    map_idx = [[31, 32], [39, 40], [33, 34], [35, 36], [41, 42], [43, 44], [19, 20], [21, 22],
               [23, 24], [25, 26], [27, 28], [29, 30], [47, 48], [49, 50], [53, 54], [51, 52],
               [55, 56], [37, 38], [45, 46]]
    # find connection in the specified sequence, center 29 is in the position 15
    limb_seq = [[2, 3], [2, 6], [3, 4], [4, 5], [6, 7], [7, 8], [2, 9], [9, 10],
                [10, 11], [2, 12], [12, 13], [13, 14], [2, 1], [1, 15], [15, 17],
                [1, 16], [16, 18], [3, 17], [6, 18]]

    colors = [[255, 0, 0], [255, 85, 0], [255, 170, 0], [255, 255, 0], [170, 255, 0], [85, 255, 0],
              [0, 255, 0], [0, 255, 85], [0, 255, 170], [0, 255, 255], [0, 170, 255], [0, 85, 255],
              [0, 0, 255], [85, 0, 255], [170, 0, 255], [255, 0, 255], [255, 0, 170], [255, 0, 85]]

    def __init__(self, weights_path, config_path, n_scales=1):
        self.weights_path = weights_path
        self.config_path = config_path
        self.params, self.model_params = self._read_config()
        self.n_scales = n_scales
        self.model = self._create_model()
        self._load_model()

    def _read_config(self):
        config = ConfigObj(self.config_path)
        param = config['param']
        model_id = param['modelID']
        model = config['models'][model_id]
        model['boxsize'] = int(model['boxsize'])
        model['stride'] = int(model['stride'])
        model['padValue'] = int(model['padValue'])
        # param['starting_range'] = float(param['starting_range'])
        # param['ending_range'] = float(param['ending_range'])
        param['octave'] = int(param['octave'])
        param['use_gpu'] = int(param['use_gpu'])
        param['starting_range'] = float(param['starting_range'])
        param['ending_range'] = float(param['ending_range'])
        param['scale_search'] = list(map(float, param['scale_search']))
        param['thre1'] = float(param['thre1'])
        param['thre2'] = float(param['thre2'])
        param['thre3'] = float(param['thre3'])
        param['mid_num'] = int(param['mid_num'])
        param['min_num'] = int(param['min_num'])
        param['crop_ratio'] = float(param['crop_ratio'])
        param['bbox_ratio'] = float(param['bbox_ratio'])
        param['GPUdeviceNumber'] = int(param['GPUdeviceNumber'])
        return param, model

    @staticmethod
    def _resize_aspect_ratio(img, img_area=250 * 250):
        ratio = float(img.shape[1]) / float(img.shape[0])
        new_h = int(np.sqrt(img_area / ratio) + 0.5)
        new_w = int((new_h * ratio) + 0.5)
        return cv2.resize(img, (new_w, new_h))

    def predict(self, img):
        """Returns keypoints, subset and candidate.

        img should be of type BGR.
        """

        t = time()
        heatmap_avg, paf_avg = self._get_hm_paf_av(img)
        all_peaks, peak_counter = self._get_peaks(heatmap_avg, self.params['thre1'])
        connection_all, special_k = self._get_connections(paf_avg, all_peaks, self.params['thre2'], img.shape)
        subset, candidate = self._get_subset(all_peaks, special_k, connection_all)
        print('Execution time: ', time() - t)
        return all_peaks, subset, candidate

    @staticmethod
    def draw_parts(canvas, peaks, subset, candidate):
        for i in range(18):
            for j in range(len(peaks[i])):
                cv2.circle(canvas, peaks[i][j][0:2], 4, OpenPose.colors[i], thickness=-1)

        stick_width = 4

        for i in range(17):
            for n in range(len(subset)):
                index = subset[n][np.array(OpenPose.limb_seq[i]) - 1]
                if -1 in index:
                    continue
                cur_canvas = canvas.copy()
                y = candidate[index.astype(int), 0]
                x = candidate[index.astype(int), 1]
                m_x = np.mean(x)
                m_y = np.mean(y)
                length = ((x[0] - x[1]) ** 2 + (y[0] - y[1]) ** 2) ** 0.5
                angle = np.degrees(np.arctan2(x[0] - x[1], y[0] - y[1]))
                polygon = cv2.ellipse2Poly((int(m_y), int(m_x)), (int(length / 2), stick_width), int(angle), 0,
                                           360, 1)
                cv2.fillConvexPoly(cur_canvas, polygon, OpenPose.colors[i])
                canvas = cv2.addWeighted(canvas, 0.4, cur_canvas, 0.6, 0)
        return canvas

    @staticmethod
    def _get_peaks(heatmap_avg, thre1):
        all_peaks = []
        peak_counter = 0

        for part in range(18):
            map_ori = heatmap_avg[:, :, part]
            _map = gaussian_filter(map_ori, sigma=3)

            map_left = np.zeros(_map.shape)
            map_left[1:, :] = _map[:-1, :]
            map_right = np.zeros(_map.shape)
            map_right[:-1, :] = _map[1:, :]
            map_up = np.zeros(_map.shape)
            map_up[:, 1:] = _map[:, :-1]
            map_down = np.zeros(_map.shape)
            map_down[:, :-1] = _map[:, 1:]

            peaks_binary = np.logical_and.reduce((_map >= map_left,
                                                  _map >= map_right,
                                                  _map >= map_up,
                                                  _map >= map_down,
                                                  _map > thre1))
            nz = np.nonzero(peaks_binary)
            peaks = list(zip(nz[1], nz[0]))  # note reverse
            peaks_with_score = [x + (map_ori[x[1], x[0]],) for x in peaks]
            _id = range(peak_counter, peak_counter + len(peaks))
            peaks_with_score_and_id = [peaks_with_score[i] + (_id[i],) for i in range(len(_id))]
            all_peaks.append(peaks_with_score_and_id)
            peak_counter += len(peaks)
        return all_peaks, peak_counter

    @staticmethod
    def _get_connections(paf_avg, all_peaks, thre2, img_shape):
        connection_all = []
        special_k = []
        mid_num = 10

        for k in range(len(OpenPose.map_idx)):
            score_mid = paf_avg[:, :, [x - 19 for x in OpenPose.map_idx[k]]]
            cand_a = all_peaks[OpenPose.limb_seq[k][0] - 1]
            cand_b = all_peaks[OpenPose.limb_seq[k][1] - 1]
            n_a = len(cand_a)
            n_b = len(cand_b)
            if n_a != 0 and n_b != 0:
                connection_candidate = []
                for i in range(n_a):
                    for j in range(n_b):
                        vec = np.subtract(cand_b[j][:2], cand_a[i][:2])
                        norm = np.sqrt(vec[0] * vec[0] + vec[1] * vec[1])
                        # failure case when 2 body parts overlaps
                        if norm == 0:
                            continue
                        vec = np.divide(vec, norm)

                        start_end = list(zip(np.linspace(cand_a[i][0], cand_b[j][0], num=mid_num),
                                             np.linspace(cand_a[i][1], cand_b[j][1], num=mid_num)))

                        vec_x = np.array(
                            [score_mid[int(round(start_end[I][1])), int(round(start_end[I][0])), 0]
                             for I in range(len(start_end))])
                        vec_y = np.array(
                            [score_mid[int(round(start_end[I][1])), int(round(start_end[I][0])), 1]
                             for I in range(len(start_end))])

                        score_mid_pts = np.multiply(vec_x, vec[0]) + np.multiply(vec_y, vec[1])
                        score_with_dist_prior = sum(score_mid_pts) / len(score_mid_pts) + min(
                            0.5 * img_shape[0] / norm - 1, 0)
                        criterion1 = len(np.nonzero(score_mid_pts > thre2)[0]) > 0.8 * len(
                            score_mid_pts)
                        criterion2 = score_with_dist_prior > 0
                        if criterion1 and criterion2:
                            connection_candidate.append([i, j, score_with_dist_prior,
                                                         score_with_dist_prior + cand_a[i][2] + cand_b[j][2]])

                connection_candidate = sorted(connection_candidate, key=lambda x: x[2], reverse=True)
                connection = np.zeros((0, 5))
                for c in range(len(connection_candidate)):
                    i, j, s = connection_candidate[c][0:3]
                    if i not in connection[:, 3] and j not in connection[:, 4]:
                        connection = np.vstack([connection, [cand_a[i][3], cand_b[j][3], s, i, j]])
                        if len(connection) >= min(n_a, n_b):
                            break

                connection_all.append(connection)
            else:
                special_k.append(k)
                connection_all.append([])
        return connection_all, special_k

    @staticmethod
    def _get_subset(all_peaks, special_k, connection_all):
        subset = -1 * np.ones((0, 20))
        candidate = np.array([item for sublist in all_peaks for item in sublist])

        for k in range(len(OpenPose.map_idx)):
            if k not in special_k:
                part_as = connection_all[k][:, 0]
                part_bs = connection_all[k][:, 1]
                index_a, index_b = np.array(OpenPose.limb_seq[k]) - 1

                for i in range(len(connection_all[k])):  # = 1:size(temp,1)
                    found = 0
                    subset_idx = [-1, -1]
                    for j in range(len(subset)):  # 1:size(subset,1):
                        if subset[j][index_a] == part_as[i] or subset[j][index_b] == part_bs[i]:
                            subset_idx[found] = j
                            found += 1

                    if found == 1:
                        j = subset_idx[0]
                        if subset[j][index_b] != part_bs[i]:
                            subset[j][index_b] = part_bs[i]
                            subset[j][-1] += 1
                            subset[j][-2] += candidate[part_bs[i].astype(int), 2] + connection_all[k][i][2]
                    elif found == 2:  # if found 2 and disjoint, merge them
                        j1, j2 = subset_idx
                        membership = ((subset[j1] >= 0).astype(int) + (subset[j2] >= 0).astype(int))[:-2]
                        if len(np.nonzero(membership == 2)[0]) == 0:  # merge
                            subset[j1][:-2] += (subset[j2][:-2] + 1)
                            subset[j1][-2:] += subset[j2][-2:]
                            subset[j1][-2] += connection_all[k][i][2]
                            subset = np.delete(subset, j2, 0)
                        else:  # as like found == 1
                            subset[j1][index_b] = part_bs[i]
                            subset[j1][-1] += 1
                            subset[j1][-2] += candidate[part_bs[i].astype(int), 2] + connection_all[k][i][2]

                    # if find no partA in the subset, create a new subset
                    elif not found and k < 17:
                        row = -1 * np.ones(20)
                        row[index_a] = part_as[i]
                        row[index_b] = part_bs[i]
                        row[-1] = 2
                        row[-2] = sum(candidate[connection_all[k][i, :2].astype(int), 2]) + connection_all[k][i][2]
                        subset = np.vstack([subset, row])

        # delete some rows of subset which has few parts occur
        delete_idx = []
        for i in range(len(subset)):
            if subset[i][-1] < 4 or subset[i][-2] / subset[i][-1] < 0.4:
                delete_idx.append(i)
        subset = np.delete(subset, delete_idx, axis=0)
        return subset, candidate

    def _get_hm_paf_av(self, img):
        """Returns heatmaps and pafs, (ims_size, 19) and (img_size, 38)"""
        multiplier = [i * self.model_params['boxsize'] / img.shape[0] for i in self.params['scale_search']]
        heatmap_avg = np.zeros((img.shape[0], img.shape[1], 19))
        paf_avg = np.zeros((img.shape[0], img.shape[1], 38))

        for m in range(len(multiplier)):
            if m >= self.n_scales:
                break
            scale = multiplier[m]

            output_blobs, padded_resized_img, pad = self._infere(img, scale)

            # extract outputs, resize, and remove padding
            heatmap = self._get_heatmap(output_blobs,
                                        self.model_params['stride'],
                                        padded_resized_img.shape,
                                        img.shape,
                                        pad)
            paf = self._get_paf(output_blobs,
                                self.model_params['stride'],
                                padded_resized_img.shape,
                                img.shape,
                                pad)

            heatmap_avg = heatmap_avg + heatmap / len(multiplier)
            paf_avg = paf_avg + paf / len(multiplier)
        return heatmap_avg, paf_avg

    def _infere(self, img, scale):
        stride = self.model_params['stride']
        pad_value = self.model_params['padValue']
        resized_img = cv2.resize(img, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        padded_resized_img, pad = self._pad_right_down_corner(resized_img, stride, pad_value)

        input_img = padded_resized_img[np.newaxis, :, :, :]
        output_blobs = self.model.predict(input_img)
        return output_blobs, padded_resized_img, pad

    @staticmethod
    def _get_heatmap(output_blobs, stride, padded_resized_shape, img_shape, pad):
        heatmap = np.squeeze(output_blobs[1])
        heatmap = cv2.resize(heatmap,
                             (0, 0),
                             fx=stride,
                             fy=stride,
                             interpolation=cv2.INTER_CUBIC)
        heatmap = heatmap[:padded_resized_shape[0] - pad[2],
                  :padded_resized_shape[1] - pad[3],
                  :]
        heatmap = cv2.resize(heatmap,
                             (img_shape[1], img_shape[0]),
                             interpolation=cv2.INTER_CUBIC)
        return heatmap

    @staticmethod
    def _get_paf(output_blobs, stride, padded_resized_shape, img_shape, pad):
        paf = np.squeeze(output_blobs[0])  # output 0 is PAFs
        paf = cv2.resize(paf,
                         (0, 0),
                         fx=stride,
                         fy=stride,
                         interpolation=cv2.INTER_CUBIC)
        paf = paf[:padded_resized_shape[0] - pad[2],
              :padded_resized_shape[1] - pad[3],
              :]
        paf = cv2.resize(paf, (img_shape[1], img_shape[0]), interpolation=cv2.INTER_CUBIC)
        return paf

    @staticmethod
    def _pad_right_down_corner(img, stride, pad_value):
        h = img.shape[0]
        w = img.shape[1]

        pad = 4 * [None]
        pad[0] = 0  # up
        pad[1] = 0  # left
        pad[2] = 0 if (h % stride == 0) else stride - (h % stride)  # down
        pad[3] = 0 if (w % stride == 0) else stride - (w % stride)  # right

        img_padded = img
        pad_up = np.tile(img_padded[0:1, :, :] * 0 + pad_value, (pad[0], 1, 1))
        img_padded = np.concatenate((pad_up, img_padded), axis=0)
        pad_left = np.tile(img_padded[:, 0:1, :] * 0 + pad_value, (1, pad[1], 1))
        img_padded = np.concatenate((pad_left, img_padded), axis=1)
        pad_down = np.tile(img_padded[-2:-1, :, :] * 0 + pad_value, (pad[2], 1, 1))
        img_padded = np.concatenate((img_padded, pad_down), axis=0)
        pad_right = np.tile(img_padded[:, -2:-1, :] * 0 + pad_value, (1, pad[3], 1))
        img_padded = np.concatenate((img_padded, pad_right), axis=1)

        return img_padded, pad

    def _create_model(self):
        input_shape = (None, None, 3)
        stages = 6
        np_branch1 = 38
        np_branch2 = 19

        input_tensor = tfkl.Input(input_shape) # Input must be RGB and (0, 255
        normalized_input = tfkl.Lambda(lambda x: x / 256 - 0.5)(input_tensor)  # [-0.5, 0.5]

        # VGG
        stage0_out = self._vgg_block(normalized_input)

        # stage 1
        stage1_branch1_out = self._stage1_block(stage0_out, np_branch1, 1)
        stage1_branch2_out = self._stage1_block(stage0_out, np_branch2, 2)
        x = tfkl.Concatenate()([stage1_branch1_out, stage1_branch2_out, stage0_out])

        # stage t >= 2
        for sn in range(2, stages + 1):
            stage_t_branch1_out = self._stage_t_block(x, np_branch1, sn, 1)
            stage_t_branch2_out = self._stage_t_block(x, np_branch2, sn, 2)
            if sn < stages:
                x = tfkl.Concatenate()([stage_t_branch1_out, stage_t_branch2_out, stage0_out])

        model = tfk.Model(input_tensor, [stage_t_branch1_out, stage_t_branch2_out])
        return model

    def _load_model(self):
        self.model.load_weights(self.weights_path)
        print('Model loaded successfully')

    def _vgg_block(self, x):
        # Block 1
        x = self._conv(x, 64, 3, "conv1_1")
        x = self._relu(x)
        x = self._conv(x, 64, 3, "conv1_2")
        x = self._relu(x)
        x = self._pooling(x, 2, 2, "pool1_1")

        # Block 2
        x = self._conv(x, 128, 3, "conv2_1")
        x = self._relu(x)
        x = self._conv(x, 128, 3, "conv2_2")
        x = self._relu(x)
        x = self._pooling(x, 2, 2, "pool2_1")

        # Block 3
        x = self._conv(x, 256, 3, "conv3_1")
        x = self._relu(x)
        x = self._conv(x, 256, 3, "conv3_2")
        x = self._relu(x)
        x = self._conv(x, 256, 3, "conv3_3")
        x = self._relu(x)
        x = self._conv(x, 256, 3, "conv3_4")
        x = self._relu(x)
        x = self._pooling(x, 2, 2, "pool3_1")

        # Block 4
        x = self._conv(x, 512, 3, "conv4_1")
        x = self._relu(x)
        x = self._conv(x, 512, 3, "conv4_2")
        x = self._relu(x)

        # Additional non vgg layers
        x = self._conv(x, 256, 3, "conv4_3_CPM")
        x = self._relu(x)
        x = self._conv(x, 128, 3, "conv4_4_CPM")
        x = self._relu(x)
        return x

    def _stage1_block(self, x, num_p, branch):
        x = self._conv(x, 128, 3, "conv5_1_CPM_L%d" % branch)
        x = self._relu(x)
        x = self._conv(x, 128, 3, "conv5_2_CPM_L%d" % branch)
        x = self._relu(x)
        x = self._conv(x, 128, 3, "conv5_3_CPM_L%d" % branch)
        x = self._relu(x)
        x = self._conv(x, 512, 1, "conv5_4_CPM_L%d" % branch)
        x = self._relu(x)
        x = self._conv(x, num_p, 1, "conv5_5_CPM_L%d" % branch)
        return x

    def _stage_t_block(self, x, num_p, stage, branch):
        x = self._conv(x, 128, 7, "Mconv1_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, 128, 7, "Mconv2_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, 128, 7, "Mconv3_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, 128, 7, "Mconv4_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, 128, 7, "Mconv5_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, 128, 1, "Mconv6_stage%d_L%d" % (stage, branch))
        x = self._relu(x)
        x = self._conv(x, num_p, 1, "Mconv7_stage%d_L%d" % (stage, branch))
        return x

    @staticmethod
    def _conv(x, nf, ks, name):
        out = tfkl.Conv2D(nf, (ks, ks), padding='same', name=name)(x)
        return out

    @staticmethod
    def _relu(x):
        return tfkl.Activation('relu')(x)

    @staticmethod
    def _pooling(x, ks, st, name):
        x = tfkl.MaxPooling2D((ks, ks), strides=(st, st), name=name)(x)
        return x


def timing(func):
    def inner(*args, **kwargs):
        t = time()
        ret = func(*args, **kwargs)
        print('{} execution time: {} s'.format(func.__name__, time() - t))
        return ret

    return inner
