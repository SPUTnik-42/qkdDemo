import numpy as np
from scipy.fft import fft, ifft
from .timeline import Timeline

class QuantumChannel(Timeline):
    """
    Quantum Optical Fiber Channel with real-time event handling.

    Models signal propagation considering:
    - Attenuation
    - Chromatic dispersion (second-order and third-order)
    - Differential group delay
    - Kerr non-linearity (Self-Phase Modulation)
    - Split-Step Fourier Method (SSFM) for simulation

    Args:
        fiber_length (float): Length of the fiber (km).
        attenuation (float): Attenuation per km (dB/km).
        beta2 (float): Second-order dispersion (ps²/km).
        beta3 (float): Third-order dispersion (ps³/km).
        dg_delay (float): Differential group delay (ps/km).
        gamma (float): Non-linear coefficient (W⁻¹·km⁻¹).
        fft_samples (int): Number of FFT samples.
        step_size (float): Step size for SSFM (km).
        timeline (Timeline): Event-driven simulation framework.
    """

    def __init__(self, 
                timeline, 
                fiber_length= 50.0, 
                attenuation= 0.2, 
                beta2=-21.27, 
                beta3= 0.12, 
                dg_delay= 0.1, 
                gamma= 1.3, 
                fft_samples= 1024, 
                step_size= 0.1 ):
        super().__init__()
        self.timeline = timeline
        self.fiber_length = fiber_length
        self.attenuation = 10 ** (-attenuation / 10)  # Convert dB/km to linear scale
        self.beta2 = beta2 * 1e-24  # Convert ps²/km to s²/m
        self.beta3 = beta3 * 1e-36  # Convert ps³/km to s³/m
        self.dg_delay = dg_delay * 1e-12  # Convert ps/km to s/m
        self.gamma = gamma
        self.fft_samples = fft_samples
        self.step_size = step_size

        # Frequency domain representation
        self.frequency_grid = np.fft.fftfreq(fft_samples, d=1e-12)  # Assume 1 ps sampling interval
        self.angular_freq = 2 * np.pi * self.frequency_grid  # Convert to angular frequency

    def dispersion_operator(self, dz):
        """
        Computes the dispersion operator in the frequency domain for a step dz.

        Args:
            dz (float): Propagation step size in km.

        Returns:
            np.ndarray: Dispersion transfer function.
        """
        w = self.angular_freq
        D = np.exp(
            -1j * (self.beta2 / 2) * (w ** 2) * dz - 1j * (self.beta3 / 6) * (w ** 3) * dz
        )
        return D

    def nonlinear_operator(self, E, dz):
        """
        Computes the non-linear phase shift (Self-Phase Modulation) for step dz.

        Args:
            E (np.ndarray): Optical field.
            dz (float): Step size (km).

        Returns:
            np.ndarray: Modified optical field.
        """
        return E * np.exp(1j * self.gamma * np.abs(E) ** 2 * dz)

    def propagate_signal(self, event_time, t, P, Ex, Ey, E):
        """
        Simulates optical signal propagation through the fiber using SSFM.

        Args:
            event_time (float): Time event was triggered.
            t (np.ndarray): Time array.
            P (np.ndarray): Optical power.
            Ex (np.ndarray): X-polarized field.
            Ey (np.ndarray): Y-polarized field.
            E (np.ndarray): Total field.
        """
        num_steps = int(self.fiber_length / self.step_size)
        dz = self.step_size

        # Convert power to amplitude
        E_complex = Ex + 1j * Ey

        for _ in range(num_steps):
            # Apply half nonlinearity
            E_complex = self.nonlinear_operator(E_complex, dz / 2)

            # Apply dispersion in frequency domain
            E_complex_f = fft(E_complex)
            E_complex_f *= self.dispersion_operator(dz)
            E_complex = ifft(E_complex_f)

            # Apply second half of nonlinearity
            E_complex = self.nonlinear_operator(E_complex, dz / 2)

            # Apply attenuation
            E_complex *= self.attenuation ** dz

        # Extract real and imaginary parts
        Ex_out, Ey_out = E_complex.real, E_complex.imag
        P_out = Ex_out ** 2 + Ey_out ** 2  # Updated Power

        print(f"[{event_time:.3e} s] Signal propagated: P_out={P_out[-1]:.2e} W")

        # Publish processed signal to next component
        self.timeline.publish(self, event_time, P_out, Ex_out, Ey_out, np.sqrt(Ex_out**2 + Ey_out**2))
