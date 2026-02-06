"""
Excel batch processing module for municipality lists
"""

import os
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import setup_logger

logger = setup_logger(__name__)

# Try to import openpyxl, fall back gracefully if not available
try:
    from openpyxl import load_workbook
    from openpyxl.worksheet.worksheet import Worksheet
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False
    logger.warning("openpyxl not installed. Excel support disabled. Install with: pip install openpyxl")


class ExcelColumnMapping(Enum):
    """Standard column mappings for municipality Excel files."""
    MUNICIPALITY_CODE = "code"
    MUNICIPALITY_NAME = "name"
    PROVINCE = "province"
    REGION = "region"
    POPULATION_TOTAL = "population_total"
    POPULATION_URBAN = "population_urban"
    POPULATION_RURAL = "population_rural"
    STATUS = "status"
    NOTES = "notes"


@dataclass
class MunicipalityRecord:
    """Single municipality record from Excel."""
    code: str
    name: str
    province: Optional[str] = None
    region: Optional[str] = None
    population_total: Optional[int] = None
    population_urban: Optional[int] = None
    population_rural: Optional[int] = None
    status: str = "pending"
    notes: Optional[str] = None
    row_number: int = 0
    extra_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "name": self.name,
            "province": self.province,
            "region": self.region,
            "population_total": self.population_total,
            "population_urban": self.population_urban,
            "population_rural": self.population_rural,
            "status": self.status,
            "notes": self.notes,
            "row_number": self.row_number,
            "extra_data": self.extra_data,
        }


@dataclass
class ExcelBatchResult:
    """Result of batch processing."""
    total_records: int
    successful: int
    failed: int
    skipped: int
    records: List[MunicipalityRecord]
    errors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.successful / self.total_records) * 100


class ExcelReader:
    """
    Reads municipality lists from Excel files for batch processing.
    """

    # Default column name mappings (case-insensitive)
    DEFAULT_COLUMN_MAPPINGS = {
        # Spanish
        "concejo": ExcelColumnMapping.MUNICIPALITY_NAME,
        "codigo": ExcelColumnMapping.MUNICIPALITY_CODE,
        "código": ExcelColumnMapping.MUNICIPALITY_CODE,
        "provincia": ExcelColumnMapping.PROVINCE,
        "region": ExcelColumnMapping.REGION,
        "región": ExcelColumnMapping.REGION,
        "habitantes": ExcelColumnMapping.POPULATION_TOTAL,
        "hab_total": ExcelColumnMapping.POPULATION_TOTAL,
        "nº total hab": ExcelColumnMapping.POPULATION_TOTAL,
        "hab_urbano": ExcelColumnMapping.POPULATION_URBAN,
        "nº hab urbano": ExcelColumnMapping.POPULATION_URBAN,
        "hab_rural": ExcelColumnMapping.POPULATION_RURAL,
        "nº hab rural": ExcelColumnMapping.POPULATION_RURAL,
        "estado": ExcelColumnMapping.STATUS,
        "notas": ExcelColumnMapping.NOTES,
        # Portuguese
        "concelho": ExcelColumnMapping.MUNICIPALITY_NAME,
        "município": ExcelColumnMapping.MUNICIPALITY_NAME,
        "municipio": ExcelColumnMapping.MUNICIPALITY_NAME,
        "distrito": ExcelColumnMapping.PROVINCE,
        "população": ExcelColumnMapping.POPULATION_TOTAL,
        "populacao": ExcelColumnMapping.POPULATION_TOTAL,
        # French
        "commune": ExcelColumnMapping.MUNICIPALITY_NAME,
        "département": ExcelColumnMapping.PROVINCE,
        "departement": ExcelColumnMapping.PROVINCE,
        "population": ExcelColumnMapping.POPULATION_TOTAL,
        # English
        "municipality": ExcelColumnMapping.MUNICIPALITY_NAME,
        "name": ExcelColumnMapping.MUNICIPALITY_NAME,
        "code": ExcelColumnMapping.MUNICIPALITY_CODE,
        "province": ExcelColumnMapping.PROVINCE,
        "status": ExcelColumnMapping.STATUS,
        "notes": ExcelColumnMapping.NOTES,
    }

    def __init__(
        self,
        file_path: str,
        sheet_name: Optional[str] = None,
        header_row: int = 1,
        custom_mappings: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize Excel reader.

        Args:
            file_path: Path to Excel file (.xlsx, .xls)
            sheet_name: Specific sheet to read (default: first sheet)
            header_row: Row number containing headers (1-indexed)
            custom_mappings: Custom column name to field mappings
        """
        if not OPENPYXL_AVAILABLE:
            raise ImportError(
                "openpyxl is required for Excel support. "
                "Install with: pip install openpyxl"
            )

        self.file_path = file_path
        self.sheet_name = sheet_name
        self.header_row = header_row
        self.custom_mappings = custom_mappings or {}
        self._workbook = None
        self._sheet = None
        self._column_map: Dict[int, ExcelColumnMapping] = {}

    def _validate_file(self) -> None:
        """Validate the Excel file exists and is readable."""
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"Excel file not found: {self.file_path}")

        ext = os.path.splitext(self.file_path)[1].lower()
        if ext not in ('.xlsx', '.xls', '.xlsm'):
            raise ValueError(f"Unsupported file format: {ext}. Use .xlsx, .xls, or .xlsm")

    def _load_workbook(self) -> None:
        """Load the Excel workbook."""
        self._validate_file()

        logger.info(f"Loading Excel file: {self.file_path}")
        self._workbook = load_workbook(self.file_path, read_only=True, data_only=True)

        if self.sheet_name:
            if self.sheet_name not in self._workbook.sheetnames:
                raise ValueError(
                    f"Sheet '{self.sheet_name}' not found. "
                    f"Available sheets: {self._workbook.sheetnames}"
                )
            self._sheet = self._workbook[self.sheet_name]
        else:
            self._sheet = self._workbook.active

        logger.info(f"Loaded sheet: {self._sheet.title}")

    def _detect_columns(self) -> None:
        """Detect and map columns based on header row."""
        if not self._sheet:
            raise RuntimeError("Workbook not loaded")

        self._column_map = {}

        for col_idx, cell in enumerate(
            self._sheet.iter_rows(min_row=self.header_row, max_row=self.header_row).__next__(),
            start=1
        ):
            if cell.value is None:
                continue

            header = str(cell.value).strip().lower()

            # Check custom mappings first
            if header in self.custom_mappings:
                field_name = self.custom_mappings[header]
                try:
                    mapping = ExcelColumnMapping(field_name)
                    self._column_map[col_idx] = mapping
                    logger.debug(f"Column {col_idx} '{header}' -> {mapping.value} (custom)")
                    continue
                except ValueError:
                    pass

            # Check default mappings
            if header in self.DEFAULT_COLUMN_MAPPINGS:
                mapping = self.DEFAULT_COLUMN_MAPPINGS[header]
                self._column_map[col_idx] = mapping
                logger.debug(f"Column {col_idx} '{header}' -> {mapping.value}")

        # Validate required columns
        required = {ExcelColumnMapping.MUNICIPALITY_NAME}
        found = set(self._column_map.values())

        if not required.issubset(found):
            missing = required - found
            raise ValueError(
                f"Required columns not found: {[m.value for m in missing]}. "
                f"Found columns: {[m.value for m in found]}"
            )

        logger.info(f"Detected {len(self._column_map)} mapped columns")

    def _parse_row(self, row, row_number: int) -> Optional[MunicipalityRecord]:
        """Parse a single row into a MunicipalityRecord."""
        data = {}
        extra = {}

        for col_idx, cell in enumerate(row, start=1):
            value = cell.value

            if col_idx in self._column_map:
                mapping = self._column_map[col_idx]
                if mapping == ExcelColumnMapping.MUNICIPALITY_CODE:
                    data["code"] = str(value).strip() if value else ""
                elif mapping == ExcelColumnMapping.MUNICIPALITY_NAME:
                    data["name"] = str(value).strip() if value else ""
                elif mapping == ExcelColumnMapping.PROVINCE:
                    data["province"] = str(value).strip() if value else None
                elif mapping == ExcelColumnMapping.REGION:
                    data["region"] = str(value).strip() if value else None
                elif mapping == ExcelColumnMapping.POPULATION_TOTAL:
                    data["population_total"] = int(value) if value else None
                elif mapping == ExcelColumnMapping.POPULATION_URBAN:
                    data["population_urban"] = int(value) if value else None
                elif mapping == ExcelColumnMapping.POPULATION_RURAL:
                    data["population_rural"] = int(value) if value else None
                elif mapping == ExcelColumnMapping.STATUS:
                    data["status"] = str(value).strip().lower() if value else "pending"
                elif mapping == ExcelColumnMapping.NOTES:
                    data["notes"] = str(value).strip() if value else None
            elif value is not None:
                # Store unmapped columns in extra_data
                extra[f"col_{col_idx}"] = value

        # Skip empty rows
        if not data.get("name"):
            return None

        # Generate code if not provided
        if not data.get("code"):
            data["code"] = f"AUTO_{row_number}"

        return MunicipalityRecord(
            row_number=row_number,
            extra_data=extra,
            **data
        )

    def read_all(self) -> List[MunicipalityRecord]:
        """
        Read all municipality records from the Excel file.

        Returns:
            List of MunicipalityRecord objects
        """
        self._load_workbook()
        self._detect_columns()

        records = []
        start_row = self.header_row + 1

        for row_idx, row in enumerate(
            self._sheet.iter_rows(min_row=start_row),
            start=start_row
        ):
            try:
                record = self._parse_row(row, row_idx)
                if record:
                    records.append(record)
            except Exception as e:
                logger.warning(f"Error parsing row {row_idx}: {e}")

        logger.info(f"Read {len(records)} municipality records")
        return records

    def read_generator(self) -> Generator[MunicipalityRecord, None, None]:
        """
        Generator that yields municipality records one at a time.
        Memory-efficient for large files.

        Yields:
            MunicipalityRecord objects
        """
        self._load_workbook()
        self._detect_columns()

        start_row = self.header_row + 1

        for row_idx, row in enumerate(
            self._sheet.iter_rows(min_row=start_row),
            start=start_row
        ):
            try:
                record = self._parse_row(row, row_idx)
                if record:
                    yield record
            except Exception as e:
                logger.warning(f"Error parsing row {row_idx}: {e}")

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary information about the Excel file.

        Returns:
            Dictionary with file summary
        """
        self._load_workbook()
        self._detect_columns()

        total_rows = self._sheet.max_row - self.header_row
        mapped_columns = [m.value for m in self._column_map.values()]

        return {
            "file_path": self.file_path,
            "sheet_name": self._sheet.title,
            "total_sheets": len(self._workbook.sheetnames),
            "available_sheets": self._workbook.sheetnames,
            "header_row": self.header_row,
            "data_rows": total_rows,
            "mapped_columns": mapped_columns,
            "total_columns": self._sheet.max_column,
        }

    def close(self) -> None:
        """Close the workbook and release resources."""
        if self._workbook:
            self._workbook.close()
            self._workbook = None
            self._sheet = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class BatchProcessor:
    """
    Processes multiple municipalities from Excel in batch.
    """

    def __init__(
        self,
        excel_reader: ExcelReader,
        process_func,
        on_progress=None,
        on_error=None,
        skip_statuses: Optional[List[str]] = None,
    ):
        """
        Initialize batch processor.

        Args:
            excel_reader: ExcelReader instance
            process_func: Function to process each record (receives MunicipalityRecord)
            on_progress: Callback for progress updates (current, total, record)
            on_error: Callback for errors (record, error)
            skip_statuses: List of statuses to skip (e.g., ["completed", "skipped"])
        """
        self.reader = excel_reader
        self.process_func = process_func
        self.on_progress = on_progress
        self.on_error = on_error
        self.skip_statuses = skip_statuses or ["completed", "success"]

    def run(self) -> ExcelBatchResult:
        """
        Run batch processing on all records.

        Returns:
            ExcelBatchResult with processing statistics
        """
        records = self.reader.read_all()
        total = len(records)

        result = ExcelBatchResult(
            total_records=total,
            successful=0,
            failed=0,
            skipped=0,
            records=records,
        )

        for idx, record in enumerate(records, start=1):
            # Check if should skip
            if record.status.lower() in self.skip_statuses:
                result.skipped += 1
                record.status = "skipped"
                logger.info(f"Skipping {record.name} (status: {record.status})")
                continue

            # Progress callback
            if self.on_progress:
                self.on_progress(idx, total, record)

            try:
                # Process the record
                self.process_func(record)
                record.status = "completed"
                result.successful += 1
                logger.info(f"Processed {record.name} successfully")

            except Exception as e:
                record.status = "failed"
                record.notes = str(e)
                result.failed += 1
                result.errors.append({
                    "record": record.to_dict(),
                    "error": str(e),
                })

                logger.error(f"Failed to process {record.name}: {e}")

                if self.on_error:
                    self.on_error(record, e)

        logger.info(
            f"Batch complete: {result.successful} success, "
            f"{result.failed} failed, {result.skipped} skipped"
        )

        return result
