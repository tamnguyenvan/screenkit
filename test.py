import cv2


img = cv2.imread('/home/tamnv/Downloads/button.png')
cv2.namedWindow('img', cv2.WINDOW_NORMAL)
cv2.imshow('img', img)
cv2.waitKey()