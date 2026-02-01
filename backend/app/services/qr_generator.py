import io
import base64
import qrcode
from qrcode.image.pil import PilImage


class QRGenerator:
    """Generate QR codes for WireGuard configurations."""

    @staticmethod
    def generate_qr_code(data: str) -> bytes:
        """Generate a QR code PNG image from data."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    @staticmethod
    def generate_qr_code_base64(data: str) -> str:
        """Generate a QR code as a base64-encoded PNG string."""
        png_bytes = QRGenerator.generate_qr_code(data)
        return base64.b64encode(png_bytes).decode()
