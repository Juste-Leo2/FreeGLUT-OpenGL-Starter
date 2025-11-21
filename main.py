import sys
from PyQt6.QtWidgets import QApplication
from src.app import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion") # Style moderne par défaut
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())