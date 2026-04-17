import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

NS_OPTIMA = "http://www.cdn.com.pl/optima/dokument"

COLOR_OK   = QColor(198, 239, 206)   # zielony — zgodne
COLOR_DIFF = QColor(255, 199, 206)   # czerwony — niezgodna ilość
COLOR_ONLY = QColor(255, 235, 156)   # żółty — tylko w jednym pliku


class DocumentPanel(QWidget):
    def __init__(self, title: str, namespace: str = "", multi_file: bool = False):
        super().__init__()
        self.namespace = namespace
        self.multi_file = multi_file
        self.aggregated: dict = {}
        self.doc_date: str = ""
        self._loaded_files: list = []
        self._total_positions: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Przyciski
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addWidget(QLabel(f"<b>{title}</b>"))
        self.btn_load = QPushButton("Wczytaj pliki..." if multi_file else "Wczytaj plik XML...")
        self.btn_load.clicked.connect(self.load_file)
        btn_layout.addWidget(self.btn_load)
        if multi_file:
            self.btn_clear = QPushButton("Wyczyść")
            self.btn_clear.clicked.connect(self._clear)
            btn_layout.addWidget(self.btn_clear)
            self.btn_edit_date = QPushButton("Zmień datę")
            self.btn_edit_date.clicked.connect(self._edit_date)
            btn_layout.addWidget(self.btn_edit_date)
        layout.addLayout(btn_layout)

        # Lista wczytanych plików
        self.file_label = QLabel("Nie wczytano pliku")
        self.file_label.setStyleSheet("color: gray; font-size: 8pt;")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        # Nagłówek dokumentu
        self.header_group = QGroupBox("Nagłówek dokumentu")
        header_layout = QVBoxLayout(self.header_group)
        header_layout.setContentsMargins(4, 4, 4, 4)
        header_layout.setSpacing(1)
        self.lbl_numer = QLabel()
        self.lbl_data = QLabel()
        self.lbl_opis = QLabel()
        self.lbl_sprzedawca = QLabel()
        self.lbl_magazyny = QLabel()
        for lbl in (self.lbl_numer, self.lbl_data, self.lbl_opis, self.lbl_sprzedawca, self.lbl_magazyny):
            header_layout.addWidget(lbl)
        layout.addWidget(self.header_group)

        # Wyszukiwanie
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.addWidget(QLabel("Szukaj:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Wpisz kod lub nazwę artykułu...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_table)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Tabela pozycji
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["LP", "Kod", "Nazwa", "Ilość (suma)"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet("QTableWidget { font-size: 9pt; }")
        layout.addWidget(self.table)

        self.lbl_summary = QLabel()
        self.lbl_summary.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(self.lbl_summary)

    # ------------------------------------------------------------------ helpers

    def _tag(self, name: str) -> str:
        return f"{{{self.namespace}}}{name}" if self.namespace else name

    def _find(self, parent, name: str):
        return parent.find(self._tag(name))

    def _text(self, parent, name: str) -> str:
        el = self._find(parent, name)
        return el.text.strip() if el is not None and el.text else ""

    # ------------------------------------------------------------------ loading

    def load_file(self):
        if self.multi_file:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Wybierz pliki XML", "", "Pliki XML (*.xml *.XML);;Wszystkie pliki (*)"
            )
            if not paths:
                return
            for path in paths:
                self._parse_file(path)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self, "Wybierz plik XML", "", "Pliki XML (*.xml *.XML);;Wszystkie pliki (*)"
            )
            if not path:
                return
            self._parse_file(path)

        self._refresh_table()

    def _clear(self):
        self.aggregated = {}
        self.doc_date = ""
        self._loaded_files = []
        self._total_positions = 0
        self.file_label.setText("Nie wczytano pliku")
        for lbl in (self.lbl_numer, self.lbl_data, self.lbl_opis, self.lbl_sprzedawca, self.lbl_magazyny):
            lbl.clear()
        self.table.setRowCount(0)
        self.lbl_summary.clear()

    def _parse_file(self, path: str):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as e:
            self.file_label.setText(f"Błąd parsowania {path}: {e}")
            return

        dokumenty = root.findall(f".//{self._tag('DOKUMENT')}")
        if not dokumenty:
            return

        # Nagłówek — wyświetl z pierwszego wczytanego pliku (lub nadpisuj przy single)
        if not self._loaded_files or not self.multi_file:
            naglowek = self._find(dokumenty[0], "NAGLOWEK")
            if naglowek is not None:
                self.doc_date = self._text(naglowek, "DATA_DOKUMENTU")
                self.lbl_numer.setText(f"Numer: {self._text(naglowek, 'NUMER_PELNY')}")
                self.lbl_data.setText(
                    f"Data dokumentu: {self._text(naglowek, 'DATA_DOKUMENTU')}  |  "
                    f"Data wystawienia: {self._text(naglowek, 'DATA_WYSTAWIENIA')}"
                )
                self.lbl_opis.setText(f"Opis: {self._text(naglowek, 'OPIS')}")
                sprzedawca = self._find(naglowek, "SPRZEDAWCA")
                if sprzedawca is not None:
                    nazwa = self._text(sprzedawca, "NAZWA")
                    nip = self._text(sprzedawca, "NIP")
                    adres = self._find(sprzedawca, "ADRES")
                    adres_str = ""
                    if adres is not None:
                        adres_str = (
                            f"{self._text(adres, 'ULICA')}, "
                            f"{self._text(adres, 'KOD_POCZTOWY')} {self._text(adres, 'MIASTO')}"
                        )
                    self.lbl_sprzedawca.setText(f"Sprzedawca: {nazwa} | NIP: {nip} | {adres_str}")
                mag_zr = self._text(naglowek, "MAGAZYN_ZRODLOWY")
                mag_doc = self._text(naglowek, "MAGAZYN_DOCELOWY")
                self.lbl_magazyny.setText(f"Magazyn źródłowy: {mag_zr}  →  Magazyn docelowy: {mag_doc}")

        # Akumulacja ilości
        if not self.aggregated:
            self.aggregated = defaultdict(lambda: {"nazwa": "", "ilosc": 0.0})

        for dok in dokumenty:
            for poz in dok.findall(f".//{self._tag('POZYCJA')}"):
                towar = self._find(poz, "TOWAR")
                if towar is None:
                    continue
                kod = self._text(towar, "KOD").upper()
                nazwa = self._text(towar, "NAZWA")
                ilosc_text = self._text(poz, "ILOSC")
                try:
                    ilosc = float(ilosc_text)
                except (ValueError, TypeError):
                    ilosc = 0.0
                self.aggregated[kod]["nazwa"] = nazwa
                self.aggregated[kod]["ilosc"] += ilosc
                self._total_positions += 1

        self._loaded_files.append(path)

        # Zaktualizuj etykietę plików
        import os
        names = [f"• {os.path.basename(p)}" for p in self._loaded_files]
        self.file_label.setText("\n".join(names))

    def _refresh_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.aggregated))
        for row, (kod, data) in enumerate(self.aggregated.items()):
            lp_item = QTableWidgetItem()
            lp_item.setData(Qt.ItemDataRole.DisplayRole, row + 1)
            self.table.setItem(row, 0, lp_item)
            self.table.setItem(row, 1, QTableWidgetItem(kod))
            self.table.setItem(row, 2, QTableWidgetItem(data["nazwa"]))
            ilosc_item = QTableWidgetItem()
            ilosc_item.setData(Qt.ItemDataRole.DisplayRole, round(data["ilosc"], 4))
            ilosc_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, ilosc_item)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.lbl_summary.setText(
            f"Pozycji: {self._total_positions}  |  "
            f"Artykułów: {len(self.aggregated)}  |  "
            f"Plików: {len(self._loaded_files)}"
        )

    def _edit_date(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Zmień datę dokumentu")
        form = QFormLayout(dlg)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        if self.doc_date:
            date_edit.setDate(QDate.fromString(self.doc_date, "yyyy-MM-dd"))
        else:
            date_edit.setDate(QDate.currentDate())
        form.addRow("Data dokumentu:", date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_date = date_edit.date().toString("yyyy-MM-dd")
            self.doc_date = new_date
            self.lbl_data.setText(
                f"Data dokumentu: {new_date}  |  Data wystawienia: {new_date}"
            )
            self._update_dates_in_files(new_date)

    def _update_dates_in_files(self, new_date: str):
        date_tags = ("DATA_DOKUMENTU", "DATA_WYSTAWIENIA", "DATA_OPERACJI")
        errors = []

        for path in self._loaded_files:
            try:
                tree = ET.parse(path)
                root = tree.getroot()
                for tag in date_tags:
                    for el in root.iter(self._tag(tag)):
                        el.text = new_date
                tree.write(path, encoding="utf-8", xml_declaration=True)
            except Exception as e:
                errors.append(f"{path}:\n{e}")

        if errors:
            QMessageBox.warning(
                self, "Błąd zapisu",
                "Nie udało się zaktualizować pliku:\n\n" + "\n\n".join(errors)
            )
        else:
            import os
            names = [os.path.basename(p) for p in self._loaded_files]
            QMessageBox.information(
                self, "Zaktualizowano datę",
                f"Data {new_date} została zapisana w {len(names)} pliku/plikach:\n" +
                "\n".join(f"• {n}" for n in names)
            )

    def _filter_table(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            kod = self.table.item(row, 1)
            nazwa = self.table.item(row, 2)
            match = (
                text in (kod.text().lower() if kod else "")
                or text in (nazwa.text().lower() if nazwa else "")
            )
            self.table.setRowHidden(row, not match)


class ComparePanel(QWidget):
    def __init__(self, panel_odoo: DocumentPanel, panel_optima: DocumentPanel):
        super().__init__()
        self.panel_odoo = panel_odoo
        self.panel_optima = panel_optima

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.addWidget(QLabel("<b>Porównanie</b>"))
        self.btn_compare = QPushButton("Porównaj")
        self.btn_compare.clicked.connect(self.run_compare)
        top_layout.addWidget(self.btn_compare)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        date_group = QGroupBox("Daty dokumentów")
        date_layout = QHBoxLayout(date_group)
        date_layout.setContentsMargins(4, 4, 4, 4)
        self.lbl_date_odoo = QLabel("ODOO: —")
        self.lbl_date_optima = QLabel("Optima: —")
        self.lbl_date_status = QLabel()
        self.lbl_date_status.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        date_layout.addWidget(self.lbl_date_odoo)
        date_layout.addWidget(QLabel("|"))
        date_layout.addWidget(self.lbl_date_optima)
        date_layout.addWidget(QLabel("|"))
        date_layout.addWidget(self.lbl_date_status)
        date_layout.addStretch()
        layout.addWidget(date_group)

        filter_layout = QHBoxLayout()
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(QLabel("Szukaj:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Wpisz kod lub nazwę...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.search_input)
        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Kod", "Nazwa", "Ilość ODOO", "Ilość Optima", "Różnica", "Status"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setStyleSheet("QTableWidget { font-size: 9pt; }")
        layout.addWidget(self.table)

        self.lbl_summary = QLabel()
        self.lbl_summary.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        layout.addWidget(self.lbl_summary)

    def run_compare(self):
        odoo = self.panel_odoo.aggregated
        optima = self.panel_optima.aggregated

        if not odoo and not optima:
            self.lbl_summary.setText("Wczytaj pliki przed porównaniem.")
            return

        date_odoo = self.panel_odoo.doc_date or "—"
        date_optima = self.panel_optima.doc_date or "—"
        self.lbl_date_odoo.setText(f"ODOO: {date_odoo}")
        self.lbl_date_optima.setText(f"Optima: {date_optima}")
        if date_odoo == date_optima and date_odoo != "—":
            self.lbl_date_status.setText("Daty zgodne")
            self.lbl_date_status.setStyleSheet("color: green;")
        else:
            self.lbl_date_status.setText("Daty różne!")
            self.lbl_date_status.setStyleSheet("color: red;")

        all_codes = sorted(set(odoo.keys()) | set(optima.keys()))

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(all_codes))

        cnt_ok = cnt_diff = cnt_only = 0

        for row, kod in enumerate(all_codes):
            in_odoo = kod in odoo
            in_optima = kod in optima
            nazwa = odoo[kod]["nazwa"] if in_odoo else optima[kod]["nazwa"]
            ilosc_odoo = odoo[kod]["ilosc"] if in_odoo else 0.0
            ilosc_optima = optima[kod]["ilosc"] if in_optima else 0.0
            roznica = round(ilosc_odoo - ilosc_optima, 4)

            if in_odoo and in_optima and roznica == 0:
                color = COLOR_OK
                status = "Zgodne"
                cnt_ok += 1
            elif in_odoo and in_optima:
                color = COLOR_DIFF
                status = "Niezgodna ilość"
                cnt_diff += 1
            else:
                color = COLOR_ONLY
                status = "Tylko ODOO" if in_odoo else "Tylko Optima"
                cnt_only += 1

            def cell(val, color=color):
                item = QTableWidgetItem(str(val))
                item.setBackground(color)
                return item

            def num_cell(val, color=color):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, val)
                item.setBackground(color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                return item

            self.table.setItem(row, 0, cell(kod))
            self.table.setItem(row, 1, cell(nazwa))
            self.table.setItem(row, 2, num_cell(round(ilosc_odoo, 4)))
            self.table.setItem(row, 3, num_cell(round(ilosc_optima, 4)))
            self.table.setItem(row, 4, num_cell(roznica))
            self.table.setItem(row, 5, cell(status))

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.lbl_summary.setText(
            f"Zgodne: {cnt_ok}  |  Niezgodna ilość: {cnt_diff}  |  Tylko w jednym pliku: {cnt_only}"
        )

    def _filter_table(self, text):
        text = text.lower()
        for row in range(self.table.rowCount()):
            kod = self.table.item(row, 0)
            nazwa = self.table.item(row, 1)
            match = (
                text in (kod.text().lower() if kod else "")
                or text in (nazwa.text().lower() if nazwa else "")
            )
            self.table.setRowHidden(row, not match)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Przeglądarka dokumentów XML")
        self.setMinimumSize(1000, 600)
        self.showMaximized()

        panel_odoo = DocumentPanel("ODOO", namespace="", multi_file=True)
        panel_optima = DocumentPanel("Optima", namespace=NS_OPTIMA, multi_file=False)
        compare_panel = ComparePanel(panel_odoo, panel_optima)

        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(panel_odoo)
        top_splitter.addWidget(panel_optima)
        top_splitter.setSizes([1, 1])

        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(compare_panel)
        main_splitter.setSizes([2, 1])

        self.setCentralWidget(main_splitter)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
