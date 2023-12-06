import cv2 as cv
import numpy as np
import pickle
import math
import time
from PIL import Image
import io
import os


def capture_image():
    cap = cv.VideoCapture(0)
    time.sleep(2)
    _, frame = cap.read()
    cap.release()
    return frame


def save_image(frame, folder_path):
    image_path = os.path.join(folder_path, f"captured_image_{time.time()}.jpg")
    cv.imwrite(image_path, frame)
    print(f"Image captured and saved: {image_path}")


def send_image(client_socket, frame):
    image = Image.fromarray(cv.cvtColor(frame, cv.COLOR_BGR2RGB))
    image_bytes = io.BytesIO()
    image.save(image_bytes, format='JPEG')
    image_bytes = image_bytes.getvalue()
    client_socket.send(str(len(image_bytes)).encode().ljust(16))
    client_socket.send(image_bytes)


def draw_labels(frame, corners, xyz, in_range, correct_rotation, shift, rotation):
    # draw labels for coordinates and distance
    x, y, z = xyz

    if in_range == "TRUE":
        range_label = "ASEP in range"
    else:
        range_label = f"ASEP out of range: Shift ASEP {shift[0]} mm {shift[1]}"
    if correct_rotation == "TRUE":
        rotation_label = "ASEP oriented correctly"
    else:
        rotation_label = f"ASEP oriented incorrectly: Rotate ASEP {rotation[0]} degrees {rotation[1]}"

    # draw frame axis, add labels for coordinates and distance
    cv.putText(frame, f"{range_label}", (20, 50), cv.FONT_HERSHEY_PLAIN, 1.5, (0, 0, 255), 2, cv.LINE_AA)
    cv.putText(frame, f"{rotation_label}", (20, 75), cv.FONT_HERSHEY_PLAIN, 1.5, (0, 0, 255), 2, cv.LINE_AA)
    cv.putText(frame, f"x: {round(x)}, y: {round(y)}, z: {round(z)}", (20, 100), cv.FONT_HERSHEY_PLAIN, 1.5,
               (0, 0, 255), 2, cv.LINE_AA)
    return frame


def draw_border(frame, corners):
    # draw border, format corner coordinate values
    cv.polylines(frame, [corners.astype(np.int32)], True, (0, 255, 255), 4, cv.LINE_AA)
    return frame


class ImageProcessing:

    def __init__(self):

        self.marker_size = 40  # marker size in mm
        self.jib_spr = 1024000  # steps per rotation of jib
        self.rail_spr = 200  # steps per rotation of rail
        self.winch_spr = 2000
        self.rail_dpr = 10.15  # distance per rotation of rail in mm
        self.winch_dpr = 100  # distance per rotation of winch in mm  50mm/1000steps = 100mm/rotation
        self.mast_to_rail = 270  # mast to rail home
        self.mast_to_camera = 341  # mast to camera origin

        self.x_camera = 481
        self.y_camera = 80
        self.z_camera = 300

        # deployment motor steps
        self.deploy_jib = 255500  # jib steps to deploy
        self.small_winch = 4000  # winch steps to lift ASEP off ground
        self.mid_winch = 6200  # winch steps to mount, louie
        self.big_winch = 15100  # winch steps to retrieval envelope, louie
        self.small_rail = 1500  # rail steps for hooking/unhooking louie
        self.mid_rail = 2500  # rail steps to mount
        self.big_rail = 5500  # rail steps to retrieval envelope

        self.deploy_2 = [self.mid_winch, self.mid_rail]

        self.deploy_3 = [self.mid_winch, self.deploy_jib, self.big_rail, self.big_winch, 2500,
                         self.big_winch, self.mid_rail + self.big_rail - 2500]

        self.asep_id = 73
        self.baseplate_ids = [4, 20, 29]
        self.center_baseplate_id = 4
        self.winch_id = 57

        # import dictionary and detection parameters
        self.marker_dict = cv.aruco.getPredefinedDictionary(cv.aruco.DICT_4X4_1000)
        self.detector_parameters = cv.aruco.DetectorParameters()
        f = open('calibration2.pkl', 'rb')
        self.camera_matrix, self.distortion = pickle.load(f)
        f.close()

    # R&D
    def detect_marker(self, target_id):
        cap = cv.VideoCapture(0)
        time.sleep(2)
        while True:
            _, frame = cap.read()
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            corners, ids, _ = cv.aruco.detectMarkers(gray, self.marker_dict, parameters=self.detector_parameters)
            if ids is not None:
                ids = ids.flatten()
                if target_id in ids:
                    index_array = np.where(ids == target_id)
                    index = index_array[0][0]
                    if index.size > 0:  # Check if the array is not empty
                        marker_id = ids[index]
                        corners = corners[index]
                    else:
                        print("Error: Marker not found")
                        marker_id = 0
                        corners = 0
                    break
        cap.release()
        return frame, marker_id, corners

    def detect_marker_calib(self, target_ids):
        cap = cv.VideoCapture(0)
        time.sleep(2)
        found = False
        while True:
            _, frame = cap.read()
            gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
            corners, ids, _ = cv.aruco.detectMarkers(gray, self.marker_dict, parameters=self.detector_parameters)
            if ids is not None:
                ids = ids.flatten()
                if len(ids) > 1:
                    for value in ids:
                        if value in target_ids:
                            index_array = np.where(ids == value)
                            index = index_array[0][0]
                            marker_id = ids[index]
                            corners = corners[index]
                            found = True
                            break
                    if found:
                        break
                else:
                    if ids[0] in target_ids:
                        marker_id = ids[0]
                        corners = corners[0]
                        break
        cap.release()
        return frame, marker_id, corners

    # R
    def marker_pose_estimation(self, corners):
        # estimate marker pose
        rvec, tvec, _ = cv.aruco.estimatePoseSingleMarkers(corners, 40, self.camera_matrix, self.distortion)
        x = tvec[0][0][0]
        y = (tvec[0][0][1]) * -1
        z = tvec[0][0][2]
        print("XYZ: " + str(x) + " " + str(y) + " " + str(z))
        x_shifted = x + self.x_camera
        xyz_shifted = [x_shifted, y, z]
        print("XYZ shifted: " + str(xyz_shifted))
        return rvec, tvec, xyz_shifted

    # R
    def rotation_shift(self, rvec, xyz_shifted):
        # shift marker pose based on rotation
        rotation_matrix, _ = cv.Rodrigues(rvec)
        rotation_angle = math.degrees(np.arcsin(rotation_matrix[1][0]))
        direction_angle = math.degrees(np.arccos(rotation_matrix[0][0]))
        print("Marker Rotation Angle:")
        print(rotation_angle)
        print("Marker Direction Angle:")
        print(direction_angle)
        x_shift = 70 * rotation_matrix[1][0]
        y_shift = 70 * math.cos(math.radians(rotation_angle))
        print("Rotation Shift: X: " + str(x_shift) + " Y: " + str(y_shift))
        x_rotated = xyz_shifted[0] - x_shift
        y_rotated = xyz_shifted[1] - y_shift
        z_rotated = xyz_shifted[2]
        xyz_rotated = [x_rotated, y_rotated, z_rotated]
        print("XYZ Rotated: " + str(xyz_rotated))
        return rotation_angle, direction_angle, xyz_rotated

    # R&D
    def draw_frame_axis(self, frame, rvec, tvec):
        # draw frame axis, add labels for coordinates and distance
        frame = cv.drawFrameAxes(frame, self.camera_matrix, self.distortion, rvec[0], tvec[0], 40, 4)
        return frame

    # R
    def check_range_rotation(self, rotation_angle, direction_angle, xyz_rotated):
        x, y, z = xyz_rotated
        y_total = y + self.mast_to_camera

        rail_distance = math.sqrt((x ** 2 + y_total ** 2)) - self.mast_to_rail
        rail_rotations = rail_distance / self.rail_dpr
        rail_steps = round(rail_rotations * self.rail_spr)
        jib_angle = math.degrees(math.atan(x / y_total))
        angle_diff = rotation_angle - jib_angle
        if rail_steps < 8000 and abs(jib_angle) < 40 and y > 150:
            print("ASEP in range")
            in_range = "TRUE"
            shift = 0
        else:
            print("ASEP out of range")
            in_range = "FALSE"
            if rail_steps > 8000:
                shift_dist = rail_steps - 8000
                shift_dir = "Forwards"
            elif abs(jib_angle) > 40:
                shift_dist = x - y_total * math.tan(math.radians(40))
                if jib_angle < 0:
                    shift_dir = "Left"
                else:
                    shift_dir = "Right"
            elif y < 150:
                shift_dist = 150 - y
                shift_dir = "Backwards"
            else:
                shift_dist = 0
                shift_dir = 0
            shift = [round(shift_dist), shift_dir]
        print("Rail steps: {} Jib angle: {} y: {}".format(rail_steps, jib_angle, y))
        if direction_angle < 80 and angle_diff < 30:
            print("ASEP in Oriented Correctly")
            correct_rotation = "TRUE"
            rotation = 0
        else:
            print("ASEP in Oriented Incorrectly")
            correct_rotation = "FALSE"
            if angle_diff < 0:
                rotation_dist = abs(angle_diff)
                rotation_dir = "CW"
            else:
                rotation_dist = angle_diff
                rotation_dir = "CCW"
            rotation = [rotation_dist, rotation_dir]
        print("Direction angle: {} Diff: {}".format(direction_angle, angle_diff))
        return in_range, correct_rotation, shift, rotation

    # D
    def check_mount(self):
        frame, marker_id, corners = self.detect_marker(self.asep_id)
        frame = draw_border(frame, corners)
        return frame

    # R
    def detect_retrieve(self):
        frame, marker_id, corners = self.detect_marker(self.asep_id)
        rvec, tvec, xyz_shifted = self.marker_pose_estimation(corners)
        rotation_angle, direction_angle, xyz_rotated = self.rotation_shift(rvec, xyz_shifted)
        in_range, correct_rotation, shift, rotation = self.check_range_rotation(rotation_angle, direction_angle, xyz_rotated)

        frame = draw_border(frame, corners)
        frame = self.draw_frame_axis(frame, rvec, tvec)
        frame = draw_labels(frame, corners, xyz_rotated, in_range, correct_rotation, shift, rotation)

        return xyz_rotated, frame, in_range, correct_rotation

    # R
    def translate_frame_retrieve(self, xyz_rotated):

        x, y, z = xyz_rotated
        y_total = y + self.mast_to_camera

        # jib
        jib_angle = math.degrees(math.atan(x / y_total))
        jib_steps = round(abs(jib_angle) * self.jib_spr / 360)
        if jib_angle < -2:
            jib_direction = 1
        else:
            jib_direction = 0

        # rail
        rail_distance = math.sqrt((x ** 2 + y_total ** 2)) - self.mast_to_rail
        rail_rotations = rail_distance / self.rail_dpr
        rail_steps = round(rail_rotations * self.rail_spr)

        if rail_steps > self.mid_rail + self.big_rail:
            clearance_rail_steps = 0
        else:
            clearance_rail_steps = self.mid_rail + self.big_rail - rail_steps
        print(clearance_rail_steps)

        retrieve1_steps = [jib_steps, rail_steps - self.small_rail, self.big_winch, self.small_rail]

        retrieve2_steps = [self.small_winch, jib_steps, clearance_rail_steps, self.big_winch - self.small_winch,
                           rail_steps + clearance_rail_steps - self.mid_rail, self.deploy_jib, self.mid_winch,
                           self.mid_rail, self.mid_winch]

        return retrieve1_steps, retrieve2_steps, jib_direction

    # R
    def recalculate_retrieval(self, xyz, direction, jib_position, rail_position):

        x, y, z = xyz
        y_total = y + self.mast_to_camera

        # jib
        jib_angle = math.degrees(math.atan(x / y_total))
        jib_steps = round(abs(jib_angle) * self.jib_spr / 360)
        if jib_angle < 0:
            jib_direction = 1
        else:
            jib_direction = 0

        # rail
        rail_distance = math.sqrt((x ** 2 + y_total ** 2)) - self.mast_to_rail
        rail_rotations = rail_distance / self.rail_dpr
        rail_steps = round(rail_rotations * self.rail_spr)
        rail_steps_new = abs(rail_steps - rail_position)
        if rail_steps > rail_position:
            rail_direction = 1
        else:
            rail_direction = 0

        winch_steps = round(self.big_winch / 2)

        new_steps = [self.small_rail, winch_steps, jib_steps, rail_steps_new, winch_steps, self.small_rail]
        new_directions = [not jib_direction, rail_direction]

        if jib_direction == 0:
            jib_sum = jib_position + jib_steps
        else:
            jib_sum = jib_position - jib_steps
        if direction == 0:
            jib_steps2 = self.deploy_jib - jib_sum
        else:
            jib_steps2 = jib_sum - self.deploy_jib

        retrieve2_steps = [self.small_winch, jib_steps2, self.big_winch - self.small_winch,
                           rail_steps - self.small_rail, self.deploy_jib, self.mid_winch, self.small_rail,
                           self.mid_winch, self.deploy_jib]

        return new_steps, new_directions, retrieve2_steps

    # CALIBRATION
    def find_baseplate_marker(self):
        cap = cv.VideoCapture(0)
        time.sleep(2)
        _, frame = cap.read()
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        corners, ids, _ = cv.aruco.detectMarkers(gray, self.marker_dict, parameters=self.detector_parameters)
        if ids is not None:
            ids = ids.flatten()
            if set(ids) & set(self.baseplate_ids):
                return True
            else:
                return False
        else:
            return False

    def center_jib(self):
        # Move the jib to the home position
        frame, marker_id, corners = self.detect_marker_calib(self.baseplate_ids)
        rvec, tvec, _ = cv.aruco.estimatePoseSingleMarkers(corners, self.marker_size, self.camera_matrix,
                                                           self.distortion)

        rotation_matrix, _ = cv.Rodrigues(rvec)
        degrees = math.degrees(np.arcsin(rotation_matrix[1][0])) + 1.35
        print(degrees)
        if marker_id == 4:
            rotation = abs(degrees)
            if degrees < 0:
                jib_direction = 1
            else:
                jib_direction = 0
            jib_steps = round((rotation / 360) * self.jib_spr)

        elif marker_id == 20:
            rotation = 90 + degrees
            jib_steps = round((rotation / 360) * self.jib_spr)
            jib_direction = 0
        elif marker_id == 29:
            rotation = 90 - degrees
            jib_steps = round((rotation / 360) * self.jib_spr)
            jib_direction = 1
        else:
            print("Error: Marker not found")
            jib_steps = 0
            jib_direction = 0

        if 1 > degrees > -1:
            jib_steps = 0

        return jib_steps, jib_direction

    def find_asep_marker(self):
        cap = cv.VideoCapture(0)
        time.sleep(2)
        _, frame = cap.read()
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        corners, ids, _ = cv.aruco.detectMarkers(gray, self.marker_dict, parameters=self.detector_parameters)
        if ids is not None:
            ids = ids.flatten()
            print(ids)
            if self.asep_id in ids:
                print("True")
                return True
            else:
                print("False")
                return False
        else:
            print("False2")
            return False

    def find_winch_marker(self):
        cap = cv.VideoCapture(0)
        time.sleep(2)
        _, frame = cap.read()
        gray = cv.cvtColor(frame, cv.COLOR_BGR2GRAY)
        corners, ids, _ = cv.aruco.detectMarkers(gray, self.marker_dict, parameters=self.detector_parameters)
        if ids is not None:
            ids = ids.flatten()
            print(ids)
            if self.winch_id in ids:
                print("True")
                return True
            else:
                print("False")
                return False
        else:
            print("False2")
            return False

    # rail to camera
    def rail_to_camera(self):
        frame, marker_id, corners = self.detect_marker(self.winch_id)
        rvec, tvec, xyz = self.marker_pose_estimation(corners)
        y_camera = (xyz[2] - 25)/8.1
        distance = y_camera - xyz[1]
        rail_steps = round((distance / self.rail_dpr) * self.rail_spr)
        if distance > 0:
            rail_direction = 1
        else:
            rail_direction = 0
        return rail_steps, rail_direction

    def tune_rail(self):
        _, _, corners = self.detect_marker(self.winch_id)
        rvec, tvec, xyz = self.marker_pose_estimation(corners)
        x, y, z = xyz
        print("y: " + str(y))
        y_camera = (xyz[2] - 25)/8.1
        print("y_camera" + str(y_camera))
        distance = y_camera - xyz[1]
        print(distance)
        if distance < 5:
            rail_tuned = True
            rail_steps = 0
            rail_direction = 0
        else:
            rail_tuned = False
            rail_steps = round((abs(distance) / self.rail_dpr) * self.rail_spr)
            if distance > 0:
                rail_direction = 1
            else:
                rail_direction = 0
        return rail_steps, rail_direction, rail_tuned

    def winch_to_camera(self):
        frame, marker_id, corners = self.detect_marker(self.winch_id)
        rvec, tvec, xyz = self.marker_pose_estimation(corners)
        x, y, z = xyz
        winch_steps = round(((z - self.z_camera) / self.winch_dpr) * self.winch_spr)
        return winch_steps

    def tune_winch(self):
        _, _, corners = self.detect_marker(self.winch_id)
        rvec, tvec, xyz = self.marker_pose_estimation(corners)
        x, y, z = xyz
        z_shifted = z - self.z_camera
        print("z: " + str(z))
        if -10 < z_shifted < 10:
            winch_tuned = True
            winch_steps = 0
            winch_direction = 0
        else:
            winch_tuned = False
            winch_steps = round((abs(z_shifted) / self.winch_dpr) * self.winch_spr)
            if z_shifted < -10:
                winch_direction = 1
            else:
                winch_direction = 0
        return winch_steps, winch_direction, winch_tuned

    def tune_jib(self):
        _, _, corners = self.detect_marker(self.center_baseplate_id)
        rvec, tvec, xyz = self.marker_pose_estimation(corners)
        rotation_matrix, _ = cv.Rodrigues(rvec)
        degrees = math.degrees(np.arcsin(rotation_matrix[1][0])) + 1.35
        print(degrees)
        rotation = abs(degrees)
        if rotation < 1:
            jib_tuned = True
            jib_steps = 0
            jib_direction = 0
        else:
            jib_tuned = False
            jib_steps = round((rotation / 360) * self.jib_spr)
            if degrees < 0:
                jib_direction = 1
            else:
                jib_direction = 0
        return jib_steps, jib_direction, jib_tuned


