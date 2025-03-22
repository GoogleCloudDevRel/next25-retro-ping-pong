import cv2
import time


def record_and_resize_video(duration=10, output_file="output.mp4", width=960, height=540):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open video capture device.")
        return

    # original_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    # original_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    # original_fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # MP4 코덱
    out = cv2.VideoWriter(output_file, fourcc, 10.0, (width, height))
    start_time = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break
        resized_frame = cv2.resize(frame, (width, height))

        out.write(resized_frame)

        cv2.imshow('frame', resized_frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        if time.time() - start_time > duration:
            break
    cap.release()
    out.release()
    cv2.destroyAllWindows()

    print(f"Video saved to {output_file}")


if __name__ == "__main__":
    record_and_resize_video()