import sys
import socket
import threading
import time
from image_processing import ImageProcessing, send_image, capture_image
from gpio_control import MotorControl

direction = 1
ret_pos = 1
left_mount = 1
right_mount = 1

rail_home_steps = 4600
winch_home_steps = 4100

xyz = []
retrieve1_steps = []
retrieve2_steps = []

process_image = ImageProcessing()


control = MotorControl()


def start_server(event):
    host = "10.224.33.39"
    port = 10000
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)

    print("Server listening on port 10000...")
    while not event.is_set():
        client_socket, addr = server.accept()
        client_handler = threading.Thread(target=handle_client, args=(client_socket,))
        client_handler.daemon = True
        client_handler.start()
    print("threading event set")
    server.close()


def handle_client(client_socket):
    global xyz, retrieve1_steps, retrieve2_steps, direction, ret_pos, left_mount, right_mount

    command = client_socket.recv(1024).decode()
    print(f"Received command: {command}")

    # Deploy left ASEP
    if command == "left_marker":
        print("Rotating jib to left ASEP")
        control.deploy_part1(1, process_image.deploy_jib)
        print("Detecting left marker")
        frame = process_image.check_mount()
        send_image(client_socket, frame)
    elif command == "approve_left_marker":
        print("Orienting to left ASEP")
        control.deploy_part2(process_image.deploy_2)
        frame = capture_image()
        send_image(client_socket, frame)
    elif command == "approve_left_deploy":
        print("Deploying left ASEP")
        control.deploy_part3(1, process_image.deploy_3)
        print("Left ASEP Deployed")
        left_mount = 0
        frame = capture_image()
        send_image(client_socket, frame)
    # Deploy right ASEP
    elif command == "right_marker":
        print("Rotating jib to right ASEP")
        control.deploy_part1(0, process_image.deploy_jib)
        print("Detecting right marker")
        frame = process_image.check_mount()
        send_image(client_socket, frame)
    elif command == "approve_right_marker":
        print("Orienting to right ASEP")
        control.deploy_part2(process_image.deploy_2)
        frame = capture_image()
        send_image(client_socket, frame)
    elif command == "approve_right_deploy":
        print("Deploying right ASEP")
        control.deploy_part3(0, process_image.deploy_3)
        print("Right ASEP Deployed")
        right_mount = 0
        frame = capture_image()
        send_image(client_socket, frame)
    # Deny deployment
    elif command == "deny_deploy_marker":
        print("Recapturing marker for deployment")
        frame = process_image.check_mount()
        send_image(client_socket, frame)
    elif command == "deny_deploy":
        print("Reorienting for deployment")
        frame = capture_image()
        send_image(client_socket, frame)
    # Retrieve ASEP
    elif command == "retrieve_marker":
        print("Detecting Marker for Retrieval")
        if left_mount == 0:
            ret_pos = 1
        elif left_mount == 1 and right_mount == 0:
            ret_pos = 0
        xyz, frame, in_range, correct_rotation = process_image.detect_retrieve()
        message = in_range + " " + correct_rotation
        client_socket.send(message.encode())
        send_image(client_socket, frame)
        if in_range == "TRUE" and correct_rotation == "TRUE":
            retrieve1_steps, retrieve2_steps, direction = process_image.translate_frame_retrieve(xyz)
    elif command == "approve_retrieve_marker":
        print("Orienting to ASEP for Retrieval")
        control.orient_for_retrieve(direction, retrieve1_steps)
        print("Tuning retrieval position")
        frame = capture_image()
        send_image(client_socket, frame)
    elif command == "approve_retrieve":
        print("Retrieving ASEP to baseplate")
        control.retrieve_asep(retrieve2_steps, ret_pos, direction)
        frame = capture_image()
        send_image(client_socket, frame)
        control.rotate_motor(control.jib_pins, steps=process_image.deploy_jib, direction=not ret_pos, delay=control.jib_delay)
    elif command == "deny_retrieve_marker":
        print("Recapturing marker for retrieval")
        xyz, frame, in_range, correct_rotation = process_image.detect_retrieve()
        message = in_range + " " + correct_rotation
        if in_range == "TRUE" and correct_rotation == "TRUE":
            retrieve1_steps, retrieve2_steps, direction = process_image.translate_frame_retrieve(xyz)
        client_socket.send(message.encode())
        send_image(client_socket, frame)
    elif command == "deny_retrieve":
        print("Reorienting for retrieval")
        control.return_from_orient(retrieve1_steps, direction)
        xyz, frame, in_range, correct_rotation = process_image.detect_retrieve()
        message = in_range + " " + correct_rotation
        client_socket.send(message.encode())
        if in_range == "TRUE" and correct_rotation == "TRUE":
            retrieve1_steps, retrieve2_steps, direction = process_image.translate_frame_retrieve(xyz)
            control.orient_for_retrieve(direction, retrieve1_steps)
        frame = capture_image()
        send_image(client_socket, frame)
    # calibration
    elif command == "crane_home":
        print("Returning crane to home position")
        while True:
            baseplate_view = process_image.find_baseplate_marker()
            if baseplate_view:
                print("Baseplate marker is in view")
                break
            else:
                print("Moving jib CCW")
                control.rotate_motor(control.jib_pins, 20000, 1, control.jib_delay)
                time.sleep(1)
        steps, direction = process_image.center_jib()
        print("Centering jib")
        control.rotate_motor(control.jib_pins, steps, direction, control.jib_delay)
        time.sleep(1)
        print("Checking ASEP inventory")
        control.rotate_motor(control.jib_pins, process_image.deploy_jib, 1, control.jib_delay)
        asep_view = process_image.find_asep_marker()
        if asep_view:
            print("Left ASEP is secured")
            left_mount = 1
        else:
            print("Left ASEP is deployed")
            left_mount = 0
        control.rotate_motor(control.jib_pins, (process_image.deploy_jib*2), 0, control.jib_delay)
        asep_view = process_image.find_asep_marker()
        if asep_view:
            print("Right ASEP is secured")
            right_mount = 1
        else:
            print("Right ASEP is deployed")
            right_mount = 0
        control.rotate_motor(control.jib_pins, process_image.deploy_jib, 1, control.jib_delay)
        winch_view = process_image.find_winch_marker()
        if winch_view:
            print("Winch is in view")
        else:
            print("Moving Rail Forward")
            control.rotate_motor(control.rail_pins, 2000, 1, control.rail_delay_slow)
            time.sleep(1)
            while True:
                winch_view = process_image.find_winch_marker()
                if winch_view:
                    print("Winch is in view")
                    break
                else:
                    print("Moving Winch down")
                    control.rotate_motor(control.winch_pins, 1000, 1, control.winch_delay_fast)
        if direction == 0:
            steps, direction = process_image.rail_to_camera()
            winch_camera_steps = process_image.winch_to_camera()
            control.rotate_motor(control.winch_pins, winch_camera_steps, 0, control.winch_delay_fast)
            control.rotate_motor(control.rail_pins, steps, 0, control.rail_delay_slow)
            control.rotate_motor(control.rail_pins, 5000, 0, control.rail_delay_slow)
            steps, direction = process_image.rail_to_camera()
        steps, direction = process_image.rail_to_camera()
        control.rotate_motor(control.rail_pins, steps, direction, control.rail_delay_slow)
        time.sleep(1)

        while True:
            steps, direction, rail_tuned = process_image.tune_rail()
            if rail_tuned:
                print("Winch is below camera")
                break
            else:
                print("Moving rail")
                control.rotate_motor(control.rail_pins, steps, direction, control.rail_delay_slow)
                time.sleep(1)

        winch_camera_steps = process_image.winch_to_camera()
        control.rotate_motor(control.winch_pins, winch_camera_steps, 0, control.winch_delay_slow)
        time.sleep(1)

        while True:
            steps, direction, winch_tuned = process_image.tune_winch()
            if winch_tuned:
                print("Winch is at home position")
                break
            else:
                print("Tuning winch")
                control.rotate_motor(control.winch_pins, steps, direction, control.winch_delay_slow)
                time.sleep(2)

        control.rotate_motor(control.winch_pins, winch_home_steps, 0, control.winch_delay_slow)
        control.rotate_motor(control.rail_pins, rail_home_steps, 0, control.rail_delay_slow)
        print("Rail is at home position")

        while True:
            steps, direction, jib_tuned = process_image.tune_jib()
            if jib_tuned:
                print("Jib is at home position")
                break
            else:
                print("Tuning jib")
                control.rotate_motor(control.jib_pins, steps, direction, control.jib_delay)
                time.sleep(2)

        print("Crane calibration complete")
        message = str(left_mount) + " " + str(right_mount)
        client_socket.send(message.encode())
        frame = capture_image()
        send_image(client_socket, frame)
    elif command == "stop_session":
        client_socket.close()
        event.is_set()
        print("Session stopped")
    else:
        pass


if __name__ == "__main__":
    event = threading.Event()
    start_server(event)
    try:
        start_server(event)
    except KeyboardInterrupt:
        # Handle keyboard interrupt (Ctrl+C)
        print("KeyboardInterrupt: Stopping the server.")
        event.set()

    finally:
        print("Exiting the program.")
        control.clean_up()
        sys.exit(0)
