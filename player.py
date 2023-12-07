from vis_nav_game import Player, Action
import pygame
import cv2
import numpy as np
import PIL.Image as Image
from skimage.metrics import structural_similarity as compare_ssim
import math



from test_simple_modified import DepthModel

# Configuration for model
config = {
    'load_weights_folder': '/Users/tangxinran/Documents/NYU/robot_perception/project/LiteMono/weights',
    'model': 'lite-mono',
    'no_cuda': True,
}

# Camera intrinsic matrix
camera_matrix = np.array([[92., 0, 160.], [0, 92., 120.], [0, 0, 1]])


    
class KeyboardPlayerPyGame(Player):
    def __init__(self):
        self.fpv = None
        self.last_act = Action.IDLE
        self.screen = None
        self.keymap = None
        self.target_image = None # The target image
        self.depth_model = DepthModel(config)  # Create an instance of DepthModel

        self.fpv_counter = 0  # Add a counter for fpv frames

        self.camera_pos = np.array([0, 0]) # x, y

        self.camera_angle = 0  # Initial orientation of the camera
        self.rotate_flag = 0   # 0: no rotation, 1: rotate right, 2: rotate left
        self.fpv_frames = []  # List of fpv frames
        self.rotate_angle = 0  # Total rotation angle


        self.initial_frame = None  # Store the initial frame for 360-degree rotation
        self.frames_angle = 0
        self.rotate_360 = True

        self.move_flag = 0  # 0: no movement, 1: move forward, 2: move backward
        self.move_step = 0  # Total movement step

        depth_info_shape = (1, 1, 192, 640)
        self.depth_info = np.ones(depth_info_shape)

        super(KeyboardPlayerPyGame, self).__init__()

    def reset(self):
        self.fpv = None
        self.last_act = Action.IDLE
        self.screen = None

        pygame.init()

        self.keymap = {
            pygame.K_LEFT: Action.LEFT,
            pygame.K_RIGHT: Action.RIGHT,
            pygame.K_UP: Action.FORWARD,
            pygame.K_DOWN: Action.BACKWARD,
            pygame.K_SPACE: Action.CHECKIN,
            pygame.K_ESCAPE: Action.QUIT
        }

    def act(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                self.last_act = Action.QUIT
                return Action.QUIT

            if event.type == pygame.KEYDOWN:
                if event.key in self.keymap:
                    self.last_act |= self.keymap[event.key]
                else:
                    self.show_target_images()
            if event.type == pygame.KEYUP:
                if event.key in self.keymap:
                    self.last_act ^= self.keymap[event.key]

        # print("self.last_act: ", self.last_act)
        if self.last_act == Action.RIGHT:
            self.rotate_flag = 1
        elif self.last_act == Action.LEFT:
            self.rotate_flag = 2
        elif self.last_act == Action.FORWARD:
            self.move_flag = 1
        elif self.last_act == Action.BACKWARD:
            self.move_flag = 2
        else:
            if len(self.fpv_frames) > 0:
                print("length of self.fpv_frames = ", len(self.fpv_frames))
                if self.rotate_flag == 1:
                    self.rotate_angle = (self.frames_angle * len(self.fpv_frames)) % (2 * math.pi)
                elif self.rotate_flag == 2:
                    self.rotate_angle = - ((self.frames_angle * len(self.fpv_frames)) % (2 * math.pi))

                self.camera_angle += self.rotate_angle
                print("camera_angle = ", self.camera_angle)
            
            if self.move_step > 0:
                if self.move_flag == 1:
                    self.camera_pos[0] += self.move_step * math.cos(self.camera_angle)
                    self.camera_pos[1] += self.move_step * math.sin(self.camera_angle)
                elif self.move_flag == 2:
                    self.camera_pos[0] -= self.move_step * math.cos(self.camera_angle)
                    self.camera_pos[1] -= self.move_step * math.sin(self.camera_angle)
                print("camera position: ", self.camera_pos)

            self.fpv_frames = []
            self.rotate_flag = 0

            self.move_step = 0
            self.move_flag = 0

        return self.last_act
    
    
    
    # Compare the similarity between two images
    def are_images_similar(self, img1, img2):
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        score, _ = compare_ssim(gray1, gray2, full=True)
        return score > 0.95  # If the similarity score is greater than 0.95, we consider the two images are similar

    def record_fpv_frame(self):
        if self.rotate_flag != 0:
            # Only calculate onces
            if self.rotate_360:
                if self.initial_frame is None:
                    self.initial_frame = self.fpv
                else:
                    if self.are_images_similar(self.initial_frame, self.fpv):
                        print(f"Completed 360-degree rotation with {len(self.fpv_frames)} frames")
                        self.frames_angle = 2 * math.pi / len(self.fpv_frames)  # Calculate the angle between each frame
                        self.initial_frame = None  # Reset
                        self.rotate_360 = False
                        return
                    
            # Append the fpv frame to the list
            self.fpv_frames.append(self.fpv)
    
    def record_move_step(self):
        if self.move_flag != 0:
            self.move_step += 1
        

    def show_target_images(self):
        targets = self.get_target_images()
        if targets is None or len(targets) <= 0:
            return
        hor1 = cv2.hconcat(targets[:2])
        hor2 = cv2.hconcat(targets[2:])
        concat_img = cv2.vconcat([hor1, hor2])

        w, h = concat_img.shape[:2]
        
        color = (0, 0, 0)

        concat_img = cv2.line(concat_img, (int(h/2), 0), (int(h/2), w), color, 2)
        concat_img = cv2.line(concat_img, (0, int(w/2)), (h, int(w/2)), color, 2)

        # TODO: should we store the concat one or all the 4 images?
        self.target_image = concat_img

        w_offset = 25
        h_offset = 10
        font = cv2.FONT_HERSHEY_SIMPLEX
        line = cv2.LINE_AA
        size = 0.75
        stroke = 1

        cv2.putText(concat_img, 'Front View', (h_offset, w_offset), font, size, color, stroke, line)
        cv2.putText(concat_img, 'Right View', (int(h/2) + h_offset, w_offset), font, size, color, stroke, line)
        cv2.putText(concat_img, 'Back View', (h_offset, int(w/2) + w_offset), font, size, color, stroke, line)
        cv2.putText(concat_img, 'Left View', (int(h/2) + h_offset, int(w/2) + w_offset), font, size, color, stroke, line)

        cv2.imshow(f'KeyboardPlayer:target_images', concat_img)
        cv2.waitKey(1)

    def set_target_images(self, images):
        super(KeyboardPlayerPyGame, self).set_target_images(images)
        self.show_target_images()

    def is_close_to_wall(self, depth_map, threshold=0.9):
        # Analyze only the central region of the depth map
        h, w = depth_map.shape[:2]
        central_region = depth_map[int(h*0.4):int(h*0.6), int(w*0.4):int(w*0.6)]

        # Calculate the mean depth in this central region
        mean_depth = np.mean(central_region)
        # print(f"Mean depth in the central region: {mean_depth}")

        return mean_depth < threshold


    def see(self, fpv):
        if fpv is None or len(fpv.shape) < 3:
            return

        self.fpv = fpv


        self.record_fpv_frame()
            
        

        if self.screen is None:
            h, w, _ = fpv.shape
            self.screen = pygame.display.set_mode((w, h))
        

        

        def convert_opencv_img_to_pygame(opencv_image):
            """
            Convert OpenCV images for Pygame.

            see https://blanktar.jp/blog/2016/01/pygame-draw-opencv-image.html
            """
            opencv_image = opencv_image[:, :, ::-1]  # BGR->RGB
            shape = opencv_image.shape[1::-1]  # (height,width,Number of colors) -> (width, height)
            pygame_image = pygame.image.frombuffer(opencv_image.tobytes(), shape, 'RGB')

            return pygame_image


        
        pygame.display.set_caption("KeyboardPlayer:fpv")
        rgb = convert_opencv_img_to_pygame(fpv)

        self.screen.blit(rgb, (0, 0))
        pygame.display.update()


        self.fpv_counter += 1
        
        if self.fpv_counter % 25 == 0:
            fpv_rgb = cv2.cvtColor(fpv, cv2.COLOR_BGR2RGB)
            rgb_image = Image.fromarray(fpv_rgb)
            self.depth_info = self.depth_model.process_image(rgb_image)
            # print("depth_info: ", depth_info)
            # print("depth_info: ", depth_info[0, 0])

        
        # Check if the camera is close to a wall
        if self.is_close_to_wall(self.depth_info[0, 0]):
            # print("Close to a wall! Stopping movement.")
            self.move_flag = 0  # Stop movement if close to a wall

        self.record_move_step()
        # print("move flag: ", self.move_flag)


if __name__ == "__main__":
    import vis_nav_game
    vis_nav_game.play(the_player=KeyboardPlayerPyGame())

