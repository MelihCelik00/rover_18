#!/usr/bin/env python
# import rospy
# from std_msgs.msg import String
# ROS
import math
import numpy as np
from random import randint
import serial
from vectorial_calculations import *
from navigation import Navigation
from fixed_destinations import AdaptiveGripperClient
import socket, errno
vz = [0, 0, 0]


class RoverArm(object):
    def __init__(self, lengths, initial=[[40, 0, 20], [1, 0, 0]]):
        self.Lengths = lengths
        self.limits = [[-180, 180], [15, 83], [55, 104], [1, 360], [-90, 90]] # [base_yaw, base_pitch, secondary_axis, gripper_pitch, gripper_rotation]
        self.joint_names = ["base_yaw", "base_pitch", "secondary_axis", "gripper_pitch", "gripper_rotation"]
        self.last_point = [0, 0, 0]
        self.degrees_to_mm = False
        self.actuator_lengths = [29.5, 29.5]
        self.navigation = Navigation(initial[0], initial[1])
        self.vectors = [vz, vz, vz]
        self.joint_angles = [0, 0, 0, 0, 0]
        self.joint_points = [vz, vz, vz]
        self.current_position = [0, 0, 0]
        self.current_direction = [0, 0, 0]
        self.serial_connected = False
        # self.update_destination_point(initial[0], initial[1])

    def check_limits(self, _joint_angles):
        count = 0
        for i in range(0, len(_joint_angles)):
            if not is_between(_joint_angles[i], self.limits[i][0], self.limits[i][1]):
                print "[ BOUNDS ERROR ] " + self.joint_names[i] + " angle({0}) is outside of bounds: ({1}, {2})".format(_joint_angles[i], self.limits[i][0], self.limits[i][1])
                # print "[ JOINT STATE CHANGE ] " + self.joint_names[i] + " angle has been changed to: {0}".format(_joint_angles[i])
                count += 1
        if count == 0:
            return True
        else:
            return False

    def print_cool_words(self):
        random1 = randint(4, 8)
        arr = []
        print "[ OK ] Joint Calculations Completed"
        arr.append("[ WARNING ] End-Point velocity has %{0} error".format(random1))
        arr.append("[ OK ] ")
        selector = randint(0, len(arr) - 1)

        print arr[selector]

    def check_distance(self, p, v):
        last_joint_vector = scalar_of_vector(v, self.Lengths[2])
        destination_point = subtract(p, last_joint_vector)
        if length(destination_point) >= self.Lengths[0] + self.Lengths[1]:
            return False
        return True

    def update_destination_point(self, point, vector):
        if not self.check_distance(point, vector):
            print "[ ERROR ] Destination is out of reach."
            return (False, None)
        if not length(vector) == 1:
            vector = make_unit(vector)
        last_joint_vector = scalar_of_vector(vector, self.Lengths[2])
        self.destination_point = point
        self.secondary_dest_point = subtract(point, last_joint_vector)
        self.direction_vector = vector
        geo = geometric_approach(self.Lengths, self.secondary_dest_point)
        v1 = rotation_u([self.Lengths[0], 0, 0], [0, -1, 0], geo[1])
        v1 = rotation_u(v1, [0, 0, 1], geo[0])
        v2 = subtract(self.secondary_dest_point, v1)
        last_angle = 180 - math.degrees(angle(vector, v2))
        first_pair_normal = cross(v2, vector)
        second_pair_normal = cross(v1, v2)
        add_axis = 180 - math.degrees(angle(first_pair_normal, second_pair_normal))
        add_axis = add_axis % 180
        # Check limits
        if not self.check_limits([geo[0], geo[1], geo[2], last_angle, add_axis]):
            _v1 = scalar_of_vector(make_unit(v1), self.Lengths[0])
            _v2 = scalar_of_vector(make_unit(v2), self.Lengths[1])
            _v3 = scalar_of_vector(vector, self.Lengths[2])
            _p1 = _v1
            _p2 = sum_vector(_v1, _v2)
            _p3 = sum_vector(_p2, _v3)
            return (False, [_p1, _p2, _p3])

        self.current_position = point
        self.current_direction = vector

        v1 = scalar_of_vector(make_unit(v1), self.Lengths[0])
        v2 = scalar_of_vector(make_unit(v2), self.Lengths[1])
        v3 = scalar_of_vector(vector, self.Lengths[2])
        self.vectors = [v1, v2, v3]
        p1 = v1
        p2 = sum_vector(v1, v2)
        p3 = sum_vector(p2, v3)
        self.joint_points = [p1, p2, p3]

        # Additional axis sign Calculation
        v_sub = subtract(self.vectors[0], self.vectors[2])
        v_sub = RotZ(v_sub, -geo[0], True)
        self.joint_angles = [geo[0], geo[1], geo[2], last_angle, -abs(add_axis)]

        if v_sub[1] >= 0:
            self.joint_angles = [geo[0], geo[1], geo[2], last_angle, abs(add_axis)]
        # INFO: self.joint_angles calculations completed

        # Store the angle only calculations
        self.joint_angle_only = [0, 0, 0, 0, 0]
        for i in range(0, 5):
            self.joint_angle_only[i] = self.joint_angles[i]

        # degrees to mm Conversion
        if self.degrees_to_mm:
            self.joint_angles[2] = (get_length_from_cos(7.5, 32.7, self.joint_angles[2]) - self.actuator_lengths[1]) * 10
            self.joint_angles[1] = (get_length_from_cos(8.124, 31.8, self.joint_angles[1] + 29.74 - 8.44) - self.actuator_lengths[0]) * 10
            # 80.62

        # self.print_cool_words()
        # Calculation of the vectorial speed of joints
        w_rot_base = 1
        w_ab = 1
        w_bc = 1
        w_cd = 1
        w_additional = 1

        # vector orientation Calculation
        normal_1 = make_unit(cross(self.vectors[0], point))
        normal_2 = make_unit(cross(self.vectors[1], sum_vector(self.vectors[1], self.vectors[2])))
        velocity_1 = make_unit(cross(normal_1, point))
        velocity_2 = make_unit(cross(sum_vector(self.vectors[1], self.vectors[2]), normal_2))
        velocity_3 = make_unit(cross(normal_2, self.vectors[2]))
        velocity_4 = normal_2
        velocity_5 = normal_1

        vel_1_scalar = w_ab * length(point)
        vel_2_scalar = w_bc * length(sum_vector(self.vectors[1], self.vectors[2]))
        vel_3_scalar = w_cd * length(self.vectors[2])
        vel_4_scalar = w_additional * math.sin(math.radians(180 - self.joint_angles[3])) * self.Lengths[2]
        vel_5_scalar = w_rot_base * math.sqrt(point[0] * point[0] + point[1] * point[1])

        velocity_1 = scalar_of_vector(velocity_1, vel_1_scalar)
        velocity_2 = scalar_of_vector(velocity_2, vel_2_scalar)
        velocity_3 = scalar_of_vector(velocity_3, vel_3_scalar)
        velocity_4 = scalar_of_vector(velocity_4, vel_4_scalar)
        velocity_5 = scalar_of_vector(velocity_5, vel_5_scalar)

        self.velocity = [velocity_1, velocity_2, velocity_3, velocity_4, velocity_5]

        self.last_point = point
        return (True, None)

    def foward_model(self, angles):
        for i in range(1, len(angles) - 1):
            angles[i] = math.radians(angles[i])
        theta2_prime = math.radians(90) + angles[1] - angles[2]
        theta4_prime = math.radians(90) - (angles[3] - theta2_prime)

        p1 = [self.Lengths[0] * math.cos(angles[1]), 0, self.Lengths[0] * math.sin(angles[1])]
        p2 = [self.Lengths[1] * math.sin(theta2_prime), 0, -self.Lengths[1] * math.cos(theta2_prime)]
        p2 = sum_vector(p1, p2)
        p3 = [self.Lengths[2] * math.cos(theta4_prime), 0, self.Lengths[2] * math.sin(theta4_prime)]
        p3 = rotation_u(p3, subtract(p2, p1), angles[4])
        p3 = sum_vector(p2, p3)

        p1 = rotation_u(p1, [0,0,1], angles[0])
        p2 = rotation_u(p2, [0,0,1], angles[0])
        p3 = rotation_u(p3, [0,0,1], angles[0])

        return [p1, p2, p3]

    # NOTE: Returning format: "base_yaw,base_pitch,secondary_axis,gripper_pitch,gripper_rotation"
    def return_model(self):
        str_msg = ""
        for i in range(0, len(self.joint_angles) - 1):
            str_msg += str(self.joint_angles[i]) + str(",")
        str_msg += str(self.joint_angles[len(self.joint_angles) - 1])
        return str_msg

    def return_model_for_low_level(self):
        # Start bit initialized
        msg = "S"
        switch_position_in_array(self.joint_angles, 3, 4)
        for i in range(0, 5):
            # Axis Number
            # msg += str(i + 1)

            # Axis angle sign 1 for + 0 for -
            if self.joint_angles[i] >= 0:
                msg += "1"
            else:
                msg += "0"

            # 3 Bit fixed size message
            value = self.joint_angles[i]
            if i == 2:
                value = 180 - value
            msg += to_fixed_size(abs(value), 3)
        switch_position_in_array(self.joint_angles, 3, 4)

        # NOTE: 6th axis calculations not completed so adding static value 0
        msg += "0000"
        print "[ WARNING ] 6th axis is set to 0."
        # Stop Bit
        msg += "F"
        return msg

    def establish_serial_connection(self, portname='/dev/cu.usbserial-A9S7BXXD', baud=115200, _timeout=0.3):
        self.ser = serial.Serial(
            # 0,
        	port=portname,
        	baudrate=baud,
            timeout=_timeout
        )
        try:
            self.ser.close()
            self.ser.open()
        except serial.SerialException:
            print "[ ERROR ] Serial port opening failed. No such serial port available, aborting!"
            self.serial_connected = False
            return
        self.serial_connected = True

    def establish_tcp(self, _timeout=1000, _host="0.0.0.0", _port=9090):
        # self.loop_rate = 1000
        try:
            self.host = _host
            self.port = _port

            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(_timeout)
            self.client.connect((self.host, self.port))
        except socket.error, e:
            print "[ ERROR ] Socket error. -> ", e

    def tcp_write(self):
        data = self.return_model_for_low_level()
        print data
        try:
            self.client.send(data + "\n")
        except socket.error, e:
            print "[ ERROR ] Socket error. -> ", e
            self.establish_tcp(5)
        except IOError, e:
            if e.errno == errno.EPIPE:
                print "[ ERROR ] Pipe error. -> ", e
                # EPIPE error
            else:
                print "[ ERROR ] Unknown Error. -> ", e
                # Other error

    def terminate_tcp(self):
        self.client.close()

    def serial_write(self):
        msg = self.return_model_for_low_level() + "\r\n"
        # msg = "HELLOWORLD!\r\n"
        # if self.ser.isOpen():
        #self.ser.write(string)
        if self.serial_connected:
            try:
                self.ser.write(msg.encode())
                self.ser.flush()
            except serial.SerialException:
                print "[ ERROR ] Serial writing failed, aborting!"
        else:
            print "[ ERROR ] Serial port closed. Establish serial connection first."

    def print_info(self):
        print "Destination Point: " + str(self.destination_point)
        print "Gripper Point: " + str(self.secondary_dest_point)
        print "Direction Vector: " + str(self.direction_vector)
        print "Segment Lengths: " + str(self.Lengths)
        print "Joint Angles[base_yaw, base_pitch, secondary_axis, gripper_pitch, gripper_rotation]: " + str(self.joint_angles)
        print "Segment Vectors: " + str(self.vectors)
        print "Joint Points: " + str(self.joint_points)


    def send_serial(self):
        mssg = self.return_model_for_low_level()
        self.joint_state_publisher.publish(mssg)


    def ros_begin(self):
        self.my_rospy = rospy
        self.joint_state_publisher = self.my_rospy.Publisher("/robotic_arm/joint_states",String,queue_size =10)
        try:
            self.my_rospy.init_node('rover_atan', anonymous=False)
        except self.my_rospy.ROSInterruptException:
            self.my_rospy.loginfo("Exception thrown")
