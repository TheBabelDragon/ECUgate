# ESP32 Hardware Strategy

ESP32-S3 is a first-class **development** compute target, not an automotive-qualified ECU.

Native: GPIO, ADC, PWM, RMT, SPI, I2C, UART, USB, TWAI classical CAN (external transceiver required).

External required: CAN transceiver, CAN FD controller, signal conditioning, protected output drivers, power protection, independent safety supervision.

Unsupported as complete ECU: native CAN FD, ASIL package, direct injector/coil drive.

Development board ≠ supervisory ≠ complete engine controller ≠ automotive-qualified controller.

Processor-independent models; S3 assumptions are not applied to all ESP32 variants.
