
import cv2
from ultralytics import YOLO
from pathlib import Path

# Create output folder
Path("outputs").mkdir(exist_ok=True)

# Load pretrained object detection model
model = YOLO("yolo11n.pt")

# Load study room image
image = cv2.imread("images/room.jpeg")

if image is None:
    raise FileNotFoundError("Room image not found")

# Detect objects
results = model(image, conf=0.25)

seat_count = 0

for box in results[0].boxes:

    class_id = int(box.cls[0])
    class_name = model.names[class_id]

    # Only detect chairs
    if class_name != "chair":
        continue

    seat_count += 1

    x1, y1, x2, y2 = map(int, box.xyxy[0])
    confidence = float(box.conf[0])

    # Draw chair bounding box
    cv2.rectangle(
        image,
        (x1, y1),
        (x2, y2),
        (0, 255, 0),
        2
    )

    # Display seat ID
    cv2.putText(
        image,
        f"S{seat_count:02d} ({confidence:.2f})",
        (x1, max(y1 - 10, 15)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (0, 255, 0),
        2
    )

    print(
        f"Seat S{seat_count:02d}: "
        f"({x1}, {y1}, {x2}, {y2}), "
        f"Confidence: {confidence:.2f}"
    )

# Save output image
cv2.imwrite("outputs/detected_seats.jpg", image)

print(f"\nTotal chairs detected: {seat_count}")

# Display result
cv2.imshow("Automatic Seat Detection", image)
cv2.waitKey(0)
cv2.destroyAllWindows()
