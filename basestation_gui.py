import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QPushButton, QLabel
from PyQt5.QtGui import QPixmap, QFont
import socket
from PyQt5.QtCore import Qt


class ClientGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.asep_stat = ["Secured", "Deploying", "Deployed", "Retrieving"]

        self.left = "Louie"
        self.right = "COPBOT"
        self.process = "start_up"
        self.left_status = "Secured"
        self.right_status = "Secured"
        self.left_mount = 1
        self.right_mount = 1
        self.ret_pos = "left"
        self.done = True
        self.init_ui()

    def init_ui(self):

        self.setGeometry(0, 0, 1920, 1120)
        self.setWindowTitle("Hyperion")
        self.setStyleSheet("background-color : #5A5A5A")

        # Create a image display object
        self.image_display = QLabel(self)  # create a label
        self.image_display.setGeometry(50, 50, 1280, 720)  # position and size
        self.image_display.setStyleSheet("border: 10px solid black")  # border style

        self.deployLeft = QPushButton('Deploy\nLeft', self)
        self.deployLeft.setGeometry(50, 900, 300, 200)
        self.deployLeft.setStyleSheet("background-color : #63c5da; border: 3px solid black")
        self.deployLeft.setFont(QFont('Arial', 30))
        self.deployLeft.clicked.connect(lambda: self.send_command("left_marker"))

        self.deployRight = QPushButton('Deploy\nRight', self)
        self.deployRight.setGeometry(425, 900, 300, 200)
        self.deployRight.setStyleSheet("background-color : #63c5da; border: 3px solid black")
        self.deployRight.setFont(QFont('Arial', 30))
        self.deployRight.clicked.connect(lambda: self.send_command("right_marker"))

        # retrieve ASEP
        self.retrieveASEP = QPushButton('Retrieve\nASEP', self)
        self.retrieveASEP.setGeometry(800, 900, 300, 200)
        self.retrieveASEP.setStyleSheet("background-color : #63c5da; border: 3px solid black")
        self.retrieveASEP.setFont(QFont('Arial', 30))
        self.retrieveASEP.clicked.connect(lambda: self.send_command('retrieve_marker'))

        # return crane home
        self.craneHome = QPushButton('Crane\nHome', self)
        self.craneHome.setGeometry(1175, 900, 300, 200)
        self.craneHome.setStyleSheet("background-color : #63c5da; border: 3px solid black")
        self.craneHome.setFont(QFont('Arial', 30))
        self.craneHome.clicked.connect(lambda: self.send_command('crane_home'))

        # approve photo
        self.approvePhoto = QPushButton('Approve', self)
        self.approvePhoto.setStyleSheet("background-color : gray; border: 3px solid black")
        self.approvePhoto.setFont(QFont('Arial', 20))
        self.approvePhoto.setGeometry(50, 780, 150, 100)
        self.approvePhoto.clicked.connect(lambda: self.approve_deny("approve_photo"))

        # deny photo
        self.denyPhoto = QPushButton('Deny', self)
        self.denyPhoto.setStyleSheet("background-color : gray; border: 3px solid black")
        self.denyPhoto.setFont(QFont('Arial', 20))
        self.denyPhoto.setGeometry(200, 780, 150, 100)
        self.denyPhoto.clicked.connect(lambda: self.approve_deny("deny_photo"))

        # stop GUI
        self.stopGUI = QPushButton('Stop\nGUI', self)
        self.stopGUI.setGeometry(1550, 900, 300, 200)
        self.stopGUI.setStyleSheet("background-color : #63c5da; border: 3px solid black")
        self.stopGUI.setFont(QFont('Arial', 30))
        self.stopGUI.clicked.connect(lambda: self.stop_session())

        # text display for left ASEP status
        self.leftStatus = QLabel(self)
        self.leftStatus.setStyleSheet("background-color : #8ddc86; border: 3px solid black")
        self.leftStatus.setAlignment(Qt.AlignCenter)
        self.leftStatus.setFont(QFont('Arial', 30))
        self.leftStatus.setGeometry(1550, 50, 300, 200)

        # text display for right ASEP status
        self.rightStatus = QLabel(self)
        self.rightStatus.setStyleSheet("background-color : #8ddc86; border: 3px solid black")
        self.rightStatus.setAlignment(Qt.AlignCenter)
        self.rightStatus.setFont(QFont('Arial', 30))
        self.rightStatus.setGeometry(1550, 270, 300, 200)

        self.status_update()
        self.button_update()

        self.show()

    def send_command(self, command):

        self.process = command
        self.done = False

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("10.224.33.39", 10000))
        client.send(command.encode())

        if command == "left_marker":
            self.left_status = "Deploying"
        elif command == "right_marker":
            self.right_status = "Deploying"
        elif command == "retrieve_marker":
            if self.left_mount == 0:
                self.left_status = "Retrieving"
                self.ret_pos = "left"
            elif self.left_mount == 1 and self.right_mount == 0:
                self.right_status = "Retrieving"
                self.ret_pos = "right"
            message = client.recv(1024).decode().split()
            print(f"ASEP in range: {message[0]} ASEP in correct rotation: {message[1]}")
            if message[0] == "FALSE" or message[1] == "FALSE":
                self.done = True
                if self.ret_pos == "right":
                    self.right_status = "Deployed"
                else:
                    self.left_status = "Deployed"
        elif command == "crane_home":
            message = client.recv(1024).decode().split()
            left_status = int(message[0])
            right_status = int(message[1])
            self.done = True

        self.receive_and_display(client)
        self.status_update()
        self.button_update()

        client.close()

    def approve_deny(self, main_command):

        process_command_map = {
            "approve_photo": {
                "left_marker": ("orient_left", "approve_left_marker"),
                "orient_left": ("deploy_left", "approve_left_deploy"),
                "right_marker": ("orient_right", "approve_right_marker"),
                "orient_right": ("deploy_right", "approve_right_deploy"),
                "retrieve_marker": ("orient_retrieve", "approve_retrieve_marker"),
                "orient_retrieve": ("retrieve_asep", "approve_retrieve")
            },
            "deny_photo": {
                "left_marker": ("left_marker", "deny_deploy_marker"),
                "orient_left": ("orient_left", "deny_deploy"),
                "right_marker": ("right_marker", "deny_deploy_marker"),
                "orient_right": ("orient_right", "deny_deploy"),
                "retrieve_marker": ("retrieve_marker", "deny_retrieve_marker"),
                "orient_retrieve": ("orient_retrieve", "deny_retrieve")
            },
        }

        process_map = process_command_map[main_command]
        process_command = process_map[self.process]
        self.process = process_command[0]
        command = process_command[1]

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("10.224.33.39", 10000))
        client.send(command.encode())

        if main_command == "approve_photo":
            if self.process == "deploy_left":
                self.left_status = "Deployed"
                self.left_mount = 0
                self.done = True
            elif self.process == "deploy_right":
                self.right_status = "Deployed"
                self.right_mount = 0
                self.done = True
            elif self.process == "retrieve_asep":
                if self.left_mount == 0:
                    self.left_status = "Secured"
                    self.left_mount = 1
                elif self.left_mount == 1 and self.right_mount == 0:
                    self.right_status = "Secured"
                    self.right_mount = 1
                self.done = True
        elif main_command == "deny_photo":
            if self.process == "retrieve_marker":
                message = client.recv(1024).decode().split()
                print(f"ASEP in range: {message[0]} ASEP in correct rotation: {message[1]}")
            if self.process == "orient_retrieve":
                message = client.recv(1024).decode().split()
                print(f"ASEP in range: {message[0]} ASEP in correct rotation: {message[1]}")
                if message[0] == "FALSE" or message[1] == "FALSE":
                    self.done = True
                    if self.ret_pos == "right":
                        self.right_status = "Deployed"
                    else:
                        self.left_status = "Deployed"
        self.receive_and_display(client)
        self.status_update()
        self.button_update()

        client.close()

    def stop_session(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("10.224.33.39", 10000))
        client.send("stop_session".encode())
        client.close()
        self.close()

    def receive_and_display(self, client):
        image_size = int(client.recv(16).strip())
        image_data = b''
        while len(image_data) < image_size:
            packet = client.recv(image_size - len(image_data))
            if not packet:
                break
            image_data += packet

        pixmap = QPixmap()
        pixmap.loadFromData(image_data)
        width = 1280
        height = 720
        scaled_pixmap = pixmap.scaled(width, height)
        self.image_display.setPixmap(scaled_pixmap)
        self.image_display.show()

    def status_update(self):
        self.leftStatus.setText("Left ASEP:\n" + self.left_status)
        self.rightStatus.setText("Right ASEP:\n" + self.right_status)

    def button_update(self):
        if self.done:
            if self.left_mount == 0:
                self.deployLeft.setEnabled(False)
            else:
                self.deployLeft.setEnabled(True)
            if self.right_mount == 0:
                self.deployRight.setEnabled(False)
            else:
                self.deployRight.setEnabled(True)
            if self.left_mount == 1 and self.right_mount == 1:
                self.retrieveASEP.setEnabled(False)
            else:
                self.retrieveASEP.setEnabled(True)
            self.craneHome.setEnabled(True)
            self.stopGUI.setEnabled(True)
            self.approvePhoto.setEnabled(False)
            self.denyPhoto.setEnabled(False)
            self.approvePhoto.setStyleSheet("background-color : gray; border: 3px solid black")
            self.denyPhoto.setStyleSheet("background-color : gray; border: 3px solid black")
        else:
            if self.process in ["left_marker", "orient_left", "right_marker", "orient_right",
                                "retrieve_marker", "orient_retrieve"]:
                self.deployLeft.setEnabled(False)
                self.deployRight.setEnabled(False)
                self.retrieveASEP.setEnabled(False)
                self.craneHome.setEnabled(False)
                self.stopGUI.setEnabled(False)
                self.approvePhoto.setEnabled(True)
                self.approvePhoto.setStyleSheet("background-color : green; border: 3px solid black")
                if self.process in ["orient_left", "orient_right"]:
                    self.denyPhoto.setEnabled(False)
                    self.denyPhoto.setStyleSheet("background-color : gray; border: 3px solid black")
                else:
                    self.denyPhoto.setEnabled(True)
                    self.denyPhoto.setStyleSheet("background-color : red; border: 3px solid black")

    def closeEvent(self, event):
        super().closeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ClientGUI()
    sys.exit(app.exec_())
