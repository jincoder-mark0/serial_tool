from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem

class PacketInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        layout.addWidget(QLabel("Packet Inspector"))
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Field", "Value"])
        
        # Dummy Data
        root = QTreeWidgetItem(self.tree)
        root.setText(0, "Packet #1")
        root.setText(1, "AT_OK")
        
        child1 = QTreeWidgetItem(root)
        child1.setText(0, "Raw")
        child1.setText(1, "OK\\r\\n")
        
        child2 = QTreeWidgetItem(root)
        child2.setText(0, "Timestamp")
        child2.setText(1, "14:30:00.123")
        
        self.tree.expandAll()
        
        layout.addWidget(self.tree)
        self.setLayout(layout)
