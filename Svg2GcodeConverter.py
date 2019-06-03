from svgpathtools import svg2paths, Line, QuadraticBezier, CubicBezier
import numpy as np
import bezier, math


def triangulate_lengths(settings, dest_xy):

    # get the desired length of the left pulley wire
    b = (settings.left_pulley_x_offset + (settings.pulley_diameter/2) + dest_xy[0])
    a = dest_xy[1] + settings.pulley_y_droop
    desired_left_line_length = math.sqrt(pow(a, 2) + pow(b, 2))

    # get the desired length of the right pulley wire
    b = (settings.right_pulley_x_offset - (settings.pulley_diameter/2) + dest_xy[0])
    a = dest_xy[1] + settings.pulley_y_droop
    desired_right_line_length = math.sqrt(pow(a, 2) + pow(b, 2))

    return desired_left_line_length, desired_right_line_length


def untriangulate_lengths(settings, x, y):
    result = [0, 0]

    if x > 0:
        result[0] = (settings.distance_between_centers * settings.distance_between_centers - y * y + x * x) / (2 * x)
    try:
        result[1] = math.sqrt(settings.distance_between_centers * settings.distance_between_centers - result[0] * result[0])
    except:
        result[1] = 10

    return result


class Svg2GcodeConverter:

    def __init__(self, settings):

        self.settings = settings

        # First cycle base case flag
        self.started = False

        self.gcode_preamble = '''
                G91         ; Set to relative mode for the initial pen lift
                G1 Z1       ; Lift head by 1
                G0 F{1}     ; Set the feed rate
                G1 Z{0}     ; Move the pen to just above the paper
                '''.format(1, self.settings.speed)

        self.gcode_end = '''
                G1 Z{0} F7000   ; Raise the pen
                '''.format(1)

    # From an input svg file, convert the vector svg paths to gcode tool paths
    def convert_gcode(self):

        # read in the svg
        paths, attributes = svg2paths("tmp/conversion-output.svg")

        # Find the scale value by resizing based on the svg bounding size
        bounding_x_max = None
        bounding_x_min = None
        bounding_y_max = None
        bounding_y_min = None

        for path in paths:

            bbox = path.bbox()

            if bounding_x_max is None:
                bounding_x_max = bbox[0]
            if bounding_x_min is None:
                bounding_x_min = bbox[1]
            if bounding_y_max is None:
                bounding_y_max = bbox[2]
            if bounding_y_min is None:
                bounding_y_min = bbox[3]

            bounding_x_min = min(bbox[0], bounding_x_min)
            bounding_x_max = max(bbox[1], bounding_x_max)

            bounding_y_min = max(bbox[2], bounding_y_min)
            bounding_y_max = max(bbox[3], bounding_y_max)

        print("Maximum X : {:.2f}".format(bounding_x_max))
        print("Minimum Y : {:.2f}".format(bounding_x_min))
        print("Maximum X : {:.2f}".format(bounding_y_max))
        print("Minimum Y : {:.2f}".format(bounding_y_min))

        max_x_dim = max(bounding_x_max, bounding_x_min)
        max_y_dim = max(bounding_y_max, bounding_y_min)

        scale_x = self.settings.canvas_x  / max_x_dim
        scale_y = self.settings.canvas_y  / max_y_dim

        scale = min(scale_x, scale_y)
        print("Scaling to : {:.5f}\n".format(scale))

        # Start the gcode
        gcode = ""
        gcode += self.gcode_preamble

        current_position = (self.settings.canvas_x/2, self.settings.pulley_y_droop)

        # Walk through the paths and create the GCODE
        for path in paths:

            previous_x = None
            previous_y = None

            for part in path:

                start = part.start
                end = part.end

                start_x = start.real * scale
                start_y = start.imag * scale

                end_x = end.real * scale
                end_y = end.imag * scale

                # Check to see if the endpoint of the last cycle continues and whether we need to lift the pen or not
                lift = True
                if previous_x is not None and previous_y is not None:
                    if abs(start.real - previous_x) < 30 and abs(start.imag - previous_y) < 30:
                        lift = False

                # if the pen needs to lift,
                # if lift:
                previous_x = end.real
                previous_y = end.imag

                if lift:
                    gcode += "G1 Z{:.3f}\n".format(1)
                else:
                    gcode += "; NOT LIFTING [{}]\n".format(self.settings.lift_counter)

                if isinstance(part, CubicBezier):

                    nodes = np.asfortranarray([
                        [start.real, part.control1.real, part.control2.real, end.real],
                        [start.imag, part.control1.imag, part.control2.imag, end.imag],
                    ])

                    curve = bezier.Curve.from_nodes(nodes)

                    evals = []
                    pos = np.linspace(0.1, 1, 3)
                    for i in pos:
                        evals.append(curve.evaluate(i))


                    #gcode += "G1 X{:.3f} Y{:.3f}\n".format(start_x, start_y)

                    lengths = triangulate_lengths(self.settings, (start_x, start_y))
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(lengths[0], lengths[1])
                    gcode += "G1 Z{:.3f} \n".format(0)

                    for i in evals:
                        x = i[0][0]
                        y = i[1][0]
                        tmp_len = triangulate_lengths(self.settings, (x * scale, y * scale))
                        gcode += "G1 X{:.3f} Y{:.3f}\n".format(tmp_len[0], tmp_len[1])

                if isinstance(part, Line):
                    start_len = triangulate_lengths(self.settings, (start_x, start_y))
                    end_len = triangulate_lengths(self.settings, (end_x, end_y))
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(start_len[0], start_len[1])
                    gcode += "G1 Z{:.3f} \n".format(0)
                    gcode += "G1 X{:.3f} Y{:.3f}\n".format(end_len[0], end_len[1])

        gcode += self.gcode_end

        output_gcode = open("output/gcode-output.gcode", "w")
        output_gcode.write(gcode)
        output_gcode.close()