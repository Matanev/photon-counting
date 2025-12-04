"""Simple SR400 photon-counting sequence for two gated measurements.

The script configures the SR400 so that counters A and B both look at
INPUT 1 with identical discriminator settings. Gate A opens immediately
for 25 ms, while Gate B opens for 25 ms starting 25 ms later. Ten
measurements are taken with one second of dwell time between runs.

Adjust ``GPIB_ADDRESS`` if your SR400 appears under a different VISA
resource name.
"""
import time
import pyvisa

GPIB_ADDRESS = "GPIB0::23::INSTR"

# SR400 constants -----------------------------------------------------------
DISCRIMINATOR_INPUT = 0  # 0=INP1, 1=INP2, 2=10 MHz, 3=TRIG
DISCRIMINATOR_LEVEL_MV = -8
DISCRIMINATOR_SLOPE = 1  # 0 = rising, 1 = falling
GATE_WIDTH_S = 0.025  # 25 ms
GATE_B_DELAY_S = 0.025  # Gate B starts 25 ms after Gate A
MEASUREMENT_COUNT = 10
DWELL_BETWEEN_RUNS_S = 1.0


def flush_buffer(sr400: pyvisa.resources.Resource) -> None:
    """Read and discard any pending bytes to avoid stale responses."""
    original_timeout = sr400.timeout
    sr400.timeout = 100
    try:
        while True:
            try:
                sr400.read()
            except Exception:
                break
    finally:
        sr400.timeout = original_timeout


def query(sr400: pyvisa.resources.Resource, cmd: str) -> str:
    """Flush the input buffer, write ``cmd``, and return the response."""
    flush_buffer(sr400)
    sr400.write(cmd)
    time.sleep(0.05)
    sr400.timeout = 500
    try:
        return sr400.read().strip().replace("\x00", "")
    finally:
        sr400.timeout = 3000


def configure_inputs(sr400: pyvisa.resources.Resource) -> None:
    """Send discriminator and input selections for both counters."""
    sr400.write(f"CI 0,{DISCRIMINATOR_INPUT}")
    sr400.write(f"CI 1,{DISCRIMINATOR_INPUT}")
    sr400.write(f"DL {DISCRIMINATOR_INPUT},{DISCRIMINATOR_LEVEL_MV}")
    sr400.write(f"DS {DISCRIMINATOR_INPUT},{DISCRIMINATOR_SLOPE}")


def configure_gates(sr400: pyvisa.resources.Resource) -> None:
    """Configure gate widths and the relative delay of gate B.

    Gate times on the SR400 are specified in 10 ns increments. Both gates are
    set to 25 ms, and Gate B starts 25 ms after Gate A.
    """
    gate_width_ticks = int(round(GATE_WIDTH_S * 1e8))
    gate_b_delay_ticks = int(round(GATE_B_DELAY_S * 1e8))

    # Gate widths (A and B) and relative delay for B
    sr400.write(f"GW {gate_width_ticks}")
    sr400.write("GA 0")
    sr400.write(f"GB {gate_b_delay_ticks}")


def configure_counting(sr400: pyvisa.resources.Resource) -> None:
    """Put the SR400 into manual start/stop counting mode."""
    sr400.write("CM 0")  # Manual start/stop
    sr400.write("NP 1")  # Single counting cycle per start


def grab_counts(sr400: pyvisa.resources.Resource) -> tuple[int, int]:
    """Return the (A, B) counts as integers."""
    count_a = int(query(sr400, "XA"))
    count_b = int(query(sr400, "XB"))
    return count_a, count_b


def perform_measurements(sr400: pyvisa.resources.Resource) -> None:
    """Run the requested set of measurements and print results."""
    total_gate_time = GATE_B_DELAY_S + GATE_WIDTH_S

    for run in range(1, MEASUREMENT_COUNT + 1):
        sr400.write("CR")  # Clear counters
        sr400.write("CS")  # Start counting

        time.sleep(total_gate_time)
        count_a, count_b = grab_counts(sr400)
        print(f"Run {run:02d}: A={count_a} counts, B={count_b} counts")

        if run < MEASUREMENT_COUNT:
            time.sleep(DWELL_BETWEEN_RUNS_S)


def main() -> None:
    rm = pyvisa.ResourceManager()
    sr400 = rm.open_resource(GPIB_ADDRESS)
    sr400.timeout = 3000
    sr400.write_termination = "\r"
    sr400.read_termination = "\r"

    try:
        configure_inputs(sr400)
        configure_gates(sr400)
        configure_counting(sr400)

        print("Configured SR400 for gated measurements on INPUT 1")
        print(
            f"Gate A width: {GATE_WIDTH_S*1e3:.1f} ms, Gate B width: {GATE_WIDTH_S*1e3:.1f} ms, "
            f"Gate B delay: {GATE_B_DELAY_S*1e3:.1f} ms"
        )
        print(f"Discriminator: {DISCRIMINATOR_LEVEL_MV} mV, slope={'falling' if DISCRIMINATOR_SLOPE else 'rising'}")

        perform_measurements(sr400)
    finally:
        sr400.close()


if __name__ == "__main__":
    main()
