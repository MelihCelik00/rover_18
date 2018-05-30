from grapher import Grapher
from vectorial_calculations import subtract, length, make_unit, scalar_of_vector, sum_vector

def generate_curve(current_position, current_direction, target_position, target_direction, iteration_factor, k1, k2, minimum_points=3):
    p1 = sum_vector(scalar_of_vector(make_unit(current_direction), -k1), current_position)
    p2 = sum_vector(scalar_of_vector(make_unit(target_direction), -k2), target_position)
    points = []


    directions = [current_direction]
    for i in [float(j) / iteration_factor for j in range(0, iteration_factor, 1)]:
        t = i
        Bx = pow((1 - t), 3) * current_position[0] + 3 * t * pow((1 - t), 2) * p1[0] + 3 * t * t * (1 - t) * p2[0] + pow(t, 3) * target_position[0]
        By = pow((1 - t), 3) * current_position[1] + 3 * t * pow((1 - t), 2) * p1[1] + 3 * t * t * (1 - t) * p2[1] + pow(t, 3) * target_position[1]
        Bz = pow((1 - t), 3) * current_position[2] + 3 * t * pow((1 - t), 2) * p1[2] + 3 * t * t * (1 - t) * p2[2] + pow(t, 3) * target_position[2]
        points.append([Bx, By, Bz])
        dir_step_v = scalar_of_vector(subtract(target_direction, current_direction), t)
        directions.append(sum_vector(current_direction, dir_step_v))
    points.append(target_position)
    directions.append(target_direction)
    avg_step_distance = 0
    for i in range(len(points) - 1):
        avg_step_distance += abs(length(subtract(points[i + 1], points[i])))
    avg_step_distance /= len(points)
    return points, directions, avg_step_distance

def generate_path(current_position, target_position, step_dist, minimum_points=3):
    movement_vector = subtract(target_position, current_position)
    distance = length(movement_vector)
    directional_vector = make_unit(movement_vector)

    number_of_points = int(distance / step_dist)
    if number_of_points == 0:
        number_of_points = minimum_points + 2
    division_distance = distance / number_of_points

    points_on_path = []
    for i in range(0, number_of_points):
        v = [0, 0, 0]
        v = scalar_of_vector(directional_vector, division_distance * (i + 1))
        v = sum_vector(v, current_position)
        points_on_path.append(v)
    return points_on_path
