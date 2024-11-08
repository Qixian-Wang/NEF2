import os

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal as sig
from scipy.integrate import simpson
from dataclasses import dataclass, field
from collections import defaultdict

from miv.core.operator.operator import OperatorMixin
from miv.core.operator.wrapper import cache_call
from miv.typing import SignalType
from MultitaperPowerSpectrum import multitaper_psd

@dataclass
class PeriodogramAnalysis(OperatorMixin):
    """
       A class to perform Periodogram Analysis using Welch's method and multitaper PSD.
       The algorithm implementation is inspired from: <https://raphaelvallat.com/bandpower.html>

       Attributes:
       -----------
       exclude_channel_list : list
           Channels to be excluded from analysis.
       band_list : list
           Frequency bands to analyze, default is [[0.5, 4], [4, 8], [8, 12], [12, 30], [30, 100]], i.e. the five common frequency bands in EEG.
       window_length_for_welch : float
           Window length in seconds for Welch's method.
    """

    exclude_channel_list: list = field(default_factory=list)
    band_list: tuple = ((0.5, 4), (4, 8), (8, 12), (12, 30), (30, 100))
    window_length_for_welch: float = 4

    tag: str = "Periodogram Analysis"

    def __post_init__(self):
        super().__init__()

    @cache_call
    def __call__(self, signal: SignalType):
        """
        Perform the periodogram analysis on the given signal.

        Parameters:
        -----------
        signal : SignalType
            Input signal to be analyzed.

        Returns:
        --------
        psd_dict:
            PSD dictionary
        power_dict
            power dictionary
        """
        psd_dict = defaultdict(dict)
        power_dict = defaultdict(dict)
        for chunk_idx, signal_piece in enumerate(signal):
            # Compute psd_dict and power_dict for welch_periodogram plotting
            psd_dict[chunk_idx] = self.computing_welch_periodogram(signal_piece)
            power_dict[chunk_idx] = self.computing_absolute_and_relative_power(psd_dict[chunk_idx])

            # Compute band power and their ratio
            self.computing_ratio_and_bandpower(signal_piece, power_dict, chunk_idx)

        return psd_dict, power_dict

    def computing_welch_periodogram(self, signal):
        """
        Compute Welch's periodogram for the signal.

        Parameters:
        -----------
        signal : SignalType
            Input signal to be analyzed.

        Returns:
        --------
        psd_dict
            Dictionary containing PSD values for all channels in this chunk.
        """
        win = self.window_length_for_welch * signal.rate
        psd_dict = defaultdict(dict)
        for channel in range(signal.number_of_channels):
            if channel in self.exclude_channel_list:
                continue
            signal_no_bias = signal.data[:, channel] - np.mean(signal.data[:, channel])
            freqs, psd = sig.welch(signal_no_bias, fs=signal.rate, nperseg=win, nfft=4*win)
            psd_dict[channel] = {
                'freqs': freqs,
                'psd': psd
            }
        return psd_dict

    def computing_absolute_and_relative_power(self, psd_dict):
        """
        Compute absolute and relative power for different frequency bands.

        Parameters:
        -----------
        psd_dict : dict
            Dictionary containing PSD values for each chunk and channel.

        Returns:
        --------
        power_dict
            Dictionary containing power values for all channels in this chunk.
        """
        bands = {
            "delta": (0.5, 4),
            "theta": (4, 8),
            "alpha": (8, 12),
            "beta": (12, 30),
            "gamma": (30, 100)
        }

        power_dict = defaultdict(dict)
        for channel in psd_dict.keys():

            freqs = psd_dict[channel]['freqs']
            psd = psd_dict[channel]['psd']
            freq_res = freqs[1] - freqs[0]

            idx_delta = np.logical_and(freqs >= bands['delta'][0], freqs <= bands['delta'][1])
            idx_theta = np.logical_and(freqs >= bands['theta'][0], freqs <= bands['theta'][1])
            idx_alpha = np.logical_and(freqs >= bands['alpha'][0], freqs <= bands['alpha'][1])
            idx_beta = np.logical_and(freqs >= bands['beta'][0], freqs <= bands['beta'][1])
            idx_gamma = np.logical_and(freqs >= bands['gamma'][0], freqs <= bands['gamma'][1])

            delta_power = simpson(psd[idx_delta], dx=freq_res)
            theta_power = simpson(psd[idx_theta], dx=freq_res)
            alpha_power = simpson(psd[idx_alpha], dx=freq_res)
            beta_power = simpson(psd[idx_beta], dx=freq_res)
            gamma_power = simpson(psd[idx_gamma], dx=freq_res)
            total_power = simpson(psd, dx=freq_res)

            delta_rel_power = delta_power / total_power
            theta_rel_power = theta_power / total_power
            alpha_rel_power = alpha_power / total_power
            beta_rel_power = beta_power / total_power
            gamma_rel_power = gamma_power / total_power

            power_dict[channel] = {
                'idx_delta': idx_delta,
                'idx_theta': idx_theta,
                'idx_alpha': idx_alpha,
                'idx_beta': idx_beta,
                'idx_gamma': idx_gamma,
                'delta_power': delta_power,
                'theta_power': theta_power,
                'alpha_power': alpha_power,
                'beta_power': beta_power,
                'gamma_power': gamma_power,
                'delta_rel_power': delta_rel_power,
                'theta_rel_power': theta_rel_power,
                'alpha_rel_power': alpha_rel_power,
                'beta_rel_power': beta_rel_power,
                'gamma_rel_power': gamma_rel_power
            }

        return power_dict

    def plot_welch_periodogram(self, output, input, show=False, save_path=None):
        """
        Plot Welch's periodogram for the given signal, w.r.t. all channels in all chunks.

        Parameters:
        -----------
        output : tuple
            Output from the __call__ method, including PSD dictionary and other information.
        show : bool
            Flag to indicate whether to show the plot.
        save_path : str
            Path to save the plot.
        """
        psd_dict = output[0]
        power_dict = output[1]

        for chunk in psd_dict.keys():
            for channel in psd_dict[chunk].keys():

                freqs = psd_dict[chunk][channel]['freqs']
                psd = psd_dict[chunk][channel]['psd']
                fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

                ax1.semilogx(freqs, psd, lw=1.5, color='k')
                ax1.set_xlabel('Frequency (Hz)')
                ax1.set_ylabel('Power spectral density (V^2 / Hz)')
                ax1.set_title(f"Welch's periodogram of channel {channel}")
                ax1.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_delta'], color='skyblue', label='Delta (0.5-4 Hz)')
                ax1.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_theta'], color='lightseagreen', label='Theta (4-8 Hz)')
                ax1.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_alpha'], color='goldenrod', label='Alpha (8-12 Hz)')
                ax1.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_beta'], color='deeppink', label='Beta (12-30 Hz)')
                ax1.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_gamma'], color='khaki', label='Gamma (30-100 Hz)')
                ax1.set_ylim([0, np.max(psd) * 1.1])
                ax1.set_xlim([1e-1, 100])
                ax1.legend()

                ax2.plot(freqs, psd, lw=1.5, color='k')
                ax2.set_xlabel('Frequency (Hz)')
                ax2.set_ylabel('Power spectral density (V^2 / Hz)')
                ax2.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_delta'], color='skyblue', label='Delta (0.5-4 Hz)')
                ax2.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_theta'], color='lightseagreen', label='Theta (4-8 Hz)')
                ax2.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_alpha'], color='goldenrod', label='Alpha (8-12 Hz)')
                ax2.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_beta'], color='deeppink', label='Beta (12-30 Hz)')
                ax2.fill_between(freqs, psd, where=power_dict[chunk][channel]['idx_gamma'], color='khaki', label='Gamma (30-100 Hz)')
                ax2.set_ylim([0, np.max(psd) * 1.1])
                ax2.set_xlim([0, 100])
                ax2.legend()

                if show:
                    plt.show()
                if save_path is not None:
                    plot_path = os.path.join(save_path, f"Chunk{chunk}_Welch_periodogram_of_channel_{channel}.png")
                    plt.savefig(plot_path, dpi=300)
                plt.close()

    def computing_ratio_and_bandpower(self, signal, power_dict, chunk_index):
        """
        Compute power ratios and band powers for specific bands using Welch's and multitaper methods.

        Parameters:
        -----------
        signal : SignalType
            Input signal to be analyzed.
        power_dict : dict
            Dictionary containing power values for each chunk and channel.
        """
        for channel in range(signal.number_of_channels):
            if channel in self.exclude_channel_list:
                continue

            self.logger.info(f"Analysis of chunk {chunk_index}, channel {channel}\n")

            band_names = ['delta', 'theta', 'alpha', 'beta', 'gamma']
            absolute_powers = [power_dict[chunk_index][channel]['delta_power'],
                                power_dict[chunk_index][channel]['theta_power'],
                                power_dict[chunk_index][channel]['alpha_power'],
                                power_dict[chunk_index][channel]['beta_power'],
                                power_dict[chunk_index][channel]['gamma_power']]

            relative_powers = [power_dict[chunk_index][channel]['delta_rel_power'],
                                power_dict[chunk_index][channel]['theta_rel_power'],
                                power_dict[chunk_index][channel]['alpha_rel_power'],
                                power_dict[chunk_index][channel]['beta_rel_power'],
                                power_dict[chunk_index][channel]['gamma_rel_power']]

            for band in self.band_list:
                multitaper_power = self.computing_multitaper_bandpower(signal, band, channel)
                multitaper_power_rel = self.computing_multitaper_bandpower(signal, band, channel, relative=True)
                self.logger.info(f"{band[0]}Hz to {band[1]}Hz: Power (absolute) (Multitaper): {multitaper_power:.3f}\n")
                self.logger.info(f"{band[0]}Hz to {band[1]}Hz: Power (relative) (Multitaper): {multitaper_power_rel:.3f}\n")

                welch_power = self.computing_welch_bandpower(signal, band, channel)
                welch_power_rel = self.computing_welch_bandpower(signal, band, channel, relative=True)

                self.logger.info(f"{band[0]}Hz to {band[1]}Hz: Power (absolute) (Welch): {welch_power:.3f}\n")
                self.logger.info(f"{band[0]}Hz to {band[1]}Hz: Power (relative) (Welch): {welch_power_rel:.3f}\n\n")

            for band, abs_power, rel_power in zip(band_names, absolute_powers, relative_powers):
                self.logger.info(f"Absolute {band} power (Welch) of channel {channel} is: {abs_power:.3f} uV^2\n")
                self.logger.info(f"Relative {band} power (Welch) of channel {channel} is: {rel_power:.3f} uV^2\n\n")

    def computing_multitaper_bandpower(self, signal, band, channel, relative=False):
        """
        Compute band power using multitaper method.

        Parameters:
        -----------
        signal : SignalType
            Input signal to be analyzed.
        band : list
            Frequency band of interest.
        channel : int
            Channel number to compute band power for.
        relative : bool
            If True, compute relative band power.

        Returns:
        --------
        float
            Computed band power.
        """
        band = np.asarray(band)
        low, high = band
        frequency = signal.rate

        psd, freqs = multitaper_psd(signal[channel], frequency)
        freq_res = freqs[1] - freqs[0]
        idx_band = np.logical_and(freqs >= low, freqs <= high)
        bp = simpson(psd[idx_band], dx=freq_res)

        if relative:
            bp /= simpson(psd, dx=freq_res)
        return bp

    def computing_welch_bandpower(self, signal, band, channel, relative=False):
        """
        Compute band power using Welch's method.

        Parameters:
        -----------
        signal : SignalType
            Input signal to be analyzed.
        band : list
            Frequency band of interest.
        channel : int
            Channel number to compute band power for.
        relative : bool
            If True, compute relative band power.

        Returns:
        --------
        float
            Computed band power.
        """
        low, high = band
        frequency = signal.rate

        if self.window_length_for_welch is not None:
            nperseg = self.window_length_for_welch * frequency 
        else:
            nperseg = (2 / low) * frequency
        freqs, psd = sig.welch(signal[channel], frequency, nperseg=nperseg)

        freq_res = freqs[1] - freqs[0]
        idx_band = np.logical_and(freqs >= low, freqs <= high)
        bp = simpson(psd[idx_band], dx=freq_res)

        if relative:
            bp /= simpson(psd, dx=freq_res)
        return bp

