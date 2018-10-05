"""
Example Code for PySource
Author: Morgan Allison
Updated: 10/18
Tests generic VSGs, UXG, and AWGs using instrument classes from PySource.
Python 3.6.4
Tested on N5182B
"""

from pySource import *

def vsg_chirp_example(ipAddress):
    """Creates downloads, assigns, and plays out a chirp waveform."""

    vsg = VSG(ipAddress, port=5025, reset=True)
    vsg.configure(rfState=1, modState=1, amp=-20, fs=50e6, iqScale=70)
    vsg.sanity_check()

    name = 'chirp'
    length = 100e-6
    bw = 40e6
    i, q = chirp_generator(length, vsg.fs, bw)

    i = np.append(i, np.zeros(5000))
    q = np.append(q, np.zeros(5000))
    vsg.write('mmemory:delete:wfm')
    vsg.download_iq_wfm(name, i, q)
    print(vsg.query('mmemory:catalog? "WFM1:"'))
    vsg.write('radio:arb:state on')
    vsg.err_check()
    vsg.disconnect()


def vsg_dig_mod_example(ipAddress):
    """Generates and plays 1 MHz 16 QAM signal with 0.35 alpha RRC filter
    @ 1 GHz CF with a generic VSG."""

    vsg = VSG(ipAddress, port=5025, timeout=15, reset=True)
    vsg.configure(rfState=1, modState=1, amp=-5, fs=50e6, iqScale=70)
    vsg.sanity_check()

    name = '1MHZ_16QAM'
    symRate = 1e6
    i, q = digmod_prbs_generator('qam16', vsg.fs, symRate)

    vsg.write('mmemory:delete:wfm')
    vsg.download_iq_wfm(name, i, q)
    print(vsg.query('mmemory:catalog? "WFM1:"'))
    vsg.write('radio:arb:state on')
    vsg.err_check()
    vsg.disconnect()


def m8190a_duc_example(ipAddress):
    """Sets up the digital upconverter on the M8190A and creates,
    downloads, assigns, and plays back a simple IQ waveform from
    the AC output port."""

    awg = M8190A(ipAddress, port=5025, reset=True)
    awg.configure(res='intx3', cf1=1e9)
    awg.sanity_check()
    i = np.ones(awg.minLen, dtype=np.int16)
    q = np.zeros(awg.minLen, dtype=np.int16)
    awg.download_iq_wfm(i, q)
    awg.write('trace:select 1')
    awg.write('output1:route ac')
    awg.write('output1:norm on')
    awg.write('init:imm')
    awg.query('*opc?')
    awg.err_check()
    awg.disconnect()


def uxg_pdw_example(ipAddress):
    """Creates and downloads a chirp waveform, defines a simple pdw csv
    file, and loads that pdw file into the UXG, and plays it out."""

    """NOTE: trigger settings may need to be adjusted for continuous
    output. This will be fixed in a future release."""

    uxg = UXG(ipAddress, port=5025, timeout=10, reset=True)
    uxg.err_check()

    uxg.write('stream:state off')
    uxg.write('radio:arb:state off')

    # Create IQ waveform
    length = 1e-6
    fs = 250e6
    chirpBw = 100e6
    i, q = chirp_generator(length, fs, chirpBw, zeroLast=True)
    wfmName = '1US_100MHz_CHIRP'
    uxg.download_iq_wfm(wfmName, i, q)

    # Define and generate csv pdw file
    pdwName = 'basic_chirp'
    fields = ['Operation', 'Time', 'Frequency', 'Zero/Hold', 'Markers', 'Name']
    data = [[1, 0, 1e9, 'Hold', '0x1', wfmName],
            [2, 10e-6, 1e9, 'Hold', '0x0', wfmName]]

    uxg.csv_pdw_file_download(pdwName, fields, data)
    uxg.write('stream:state on')
    uxg.write('stream:trigger:play:immediate')
    uxg.err_check()
    uxg.disconnect()


def uxg_lan_streaming_example(ipAddress):
    """Creates and downloads iq waveforms & a waveform index file,
    builds a PDW file, configures LAN streaming, and streams the PDWs
    to the UXG."""

    uxg = UXG(ipAddress, port=5025, timeout=10, reset=True)
    uxg.err_check()

    # Waveform creation, three chirps of the same bandwidth and different lengths
    lengths = [10e-6, 50e-6, 100e-6]
    wfmNames = []
    for l in lengths:
        i, q = chirp_generator(l, fs=250e6, chirpBw=100e6, zeroLast=True)
        uxg.download_iq_wfm(f'{l}_100MHz_CHIRP', i, q)
        wfmNames.append(f'{l}_100MHz_CHIRP')

    # Create/download waveform index file
    windex = {'fileName': 'chirps', 'wfmNames': wfmNames}
    uxg.csv_windex_file_download(windex)

    # Create PDWs
    # operation, freq, phase, startTimeSec, power, markers,
    # phaseControl, rfOff, wIndex, wfmMkrMask
    rawPdw = [[1, 1e9, 0, 0,      0, 1, 0, 0, 0, 0xF],
              [0, 1e9, 0, 20e-6, 0, 0, 0, 0, 1, 0xF],
              [0, 1e9, 0, 120e-6, 0, 0, 0, 0, 2, 0xF],
              [2, 1e9, 0, 300e-6, 0, 0, 0, 0, 2, 0xF]]

    pdwFile = uxg.bin_pdw_file_builder(rawPdw)

    # Separate pdwFile into header and data portions
    header = pdwFile[:4096]
    data = pdwFile[4096:]

    uxg.write('stream:markers:pdw1:mode stime')
    uxg.write('rout:trigger2:output pmarker1')
    uxg.write('stream:source lan')
    uxg.write('stream:trigger:play:file:type continuous')
    uxg.write('stream:trigger:play:file:type:continuous:type trigger')
    uxg.write('stream:trigger:play:source bus')
    uxg.write(f'memory:import:windex "{windex["fileName"]}.csv","{windex["fileName"]}"')
    uxg.write(f'stream:windex:select "{windex["fileName"]}"')

    uxg.write('stream:external:header:clear')

    # The esr=False argument allows you to send your own read/query after binblockwrite
    uxg.binblockwrite(f'stream:external:header? ', header, esr=False)
    if uxg.query('') != '+0':
        raise VsgError('stream:external:header? response invalid. This should never happen if file was built correctly.')

    # Configure LAN streaming and send PDWs
    uxg.write('stream:state on')
    uxg.open_lan_stream()
    uxg.lanStream.send(data)

    # Ensure everything is synchronized
    uxg.query('*opc?')

    # Begin streaming
    uxg.write('stream:trigger:play:immediate')

    # Waiting for stream to finish, turn off stream, close stream port
    uxg.query('*opc?')
    uxg.write('stream:state off')
    uxg.close_lan_stream()

    # Check for errors and gracefully disconnect.
    uxg.err_check()
    uxg.disconnect()


def main():
    # m8190a_example('141.121.210.171')
    vsg_chirp_example('169.254.224.223')
    # uxg_example('141.121.210.167')
    # uxg_lan_streaming_example('141.121.210.167')
    # vsg_dig_mod_example('169.254.224.223')


if __name__ == '__main__':
    main()
