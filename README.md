# FZ-VIS: A Visual Analytics Framework for Quantities-of-Interest-Aware Scientific Lossy Compression

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![OSF Supplemental Materials](https://img.shields.io/badge/OSF-Supplemental%20Materials-337ab7)](https://osf.io/7cspq)
[![Video Demos](https://img.shields.io/badge/Video-Demos-2ea44f)](#system-workflow--interface-overview)

**FZ-VIS** is a web-based, human-in-the-loop visual analytics framework for designing, comparing, and refining Quantities-of-Interest (QoI)-aware scientific lossy compression workflows. Built on top of [LibPressio](https://github.com/robertu94/libpressio), FZ-VIS tightly couples the **compressor design space** with the **scientific evaluation space**, enabling users to compose compressor pipelines, run configuration sweeps, inspect intermediate pipeline artifacts, and evaluate topological and spectral fidelity alongside standard rate-distortion metrics.

---

## System Workflow & Interface Overview

FZ-VIS organizes compression exploration into iterative workflow composition and linked visual/quantitative analysis across a split-pane workspace:

### 1. Setup & Workflow Composition (`Workflow Graph` — Left Pane)
Drag and connect pipeline components from the **Pipeline Components** palette onto the **Workflow Graph**, or export/import complete workflow specifications as JSON for reproducibility:
- **Data Source**: Upload or select datasets (`.bin`, `.raw`, `.npy`, `.nc`/NetCDF) with grid dimensions, floating-point precision, and NetCDF variable selection. Sample datasets are available in [`datasets/`](./datasets).
- **Data Filters**: Preprocess input fields with **Clip**, **Threshold Mask**, and **Normalize** (min-max normalization).
- **Compressor Configs**: Configure **SZ3** (predictor, quantizer, encoder, lossless backend) and **ZFP** pipelines, or promote a pipeline to the **Configuration Graph** (parallel coordinates + force-directed graph with parameter and execution propagation across error bounds).
- **Correction Modules**: Attach post hoc QoI correction nodes directly downstream of compressed outputs:
  - **Morse-Smale Segmentation Correction ([MSz](https://github.com/YuxiaoLi1234/MSz))**: Edit-based correction preserving piecewise linear Morse-Smale segmentations under global error bounds.
  - **FFCz Frequency Correction ([FFCz](https://github.com/guoxil/FFCz))**: Dual spatial/frequency error-bounded correction with frequency bound sweeping to preserve the power spectrum $P(k)$.

**Demo - Interactive Compressor Workflow Composition**

<video src="./docs/media/requirement1-demo.mp4" controls preload="metadata" width="100%"></video>

**Demo — Parameter Space Exploration (`Configuration Graph`)**

<video src="./docs/media/requirement2-demo.mp4" controls preload="metadata" width="100%"></video>

### 2. Linked Visual & Quantitative Analysis (Right Pane)
- **Data Visualization**: Interactive side-by-side spatial views of original data, decompressed reconstructions, and pointwise error maps, supporting slice inspection, colormap customization, ROI selection and localized metric evaluation, and critical point overlays (minima, maxima, saddles).
- **Metrics & Analysis**:
  - **Compression Metrics**: Customizable scatter plots (e.g., PSNR vs. Bit Rate, DSSIM vs. Error Bound, Overall Compression Ratio vs. Error Bound), grouped metric bar charts with physical units, and filterable raw metric tables.
  - **Data Analysis**: Compute **Statistical Summary**, **DSSIM**, **Power Spectrum** (with spectrum relative error and interactive frequency ROI), and **Critical Points / Morse-Smale Segmentation** fault counts across selected compressed and corrected data sources.
- **Developer (`SZ3 Debugging Study`)**: Register or upload exported SZ3 debugging studies to compare prediction residual histograms, quantization index distributions, stage-wise runtime breakdowns (`prediction`, `quantization`, `encoding`, `lossless`), throughput, and spatial slices.

**Demo — Profiling Compressors via Linked Analysis Views**

<video src="./docs/media/requirement4-demo.mp4" controls preload="metadata" width="100%"></video>

**Demo — Analyzing and Preserving QoI-Driven Fidelity**

<video src="./docs/media/requirement5-demo.mp4" controls preload="metadata" width="100%"></video>


---

## Installation & Quick Start

FZ-VIS provides an automated installer that sets up Spack, `libpressio` (with SZ3, ZFP, FPZIP, and MGARD), Python dependencies, the Vue.js frontend, and optional QoI correction modules (`MSz` and `FFCz`).

### Quick Install

```sh
git clone https://github.com/YuxiaoLi1234/fzvis.git
cd fzvis
./scripts/install_fzvis.sh
```

### Run FZ-VIS

After running the installation script, simply run the following command:
```sh
./scripts/run_fzvis.sh
```

Then open the interface in your browser (default port `10080`):

```text
http://localhost:10080
```

---

## Citation

If you use FZ-VIS in your research, please cite our paper:

```bibtex
@article{liu2026fzvis,
  title={{FZ-VIS}: A Visual Analytics Framework for Quantities-of-Interest-Aware Scientific Lossy Compression},
  author={Liu, Guoxi and Li, Yuxiao and Ren, Congrong and Underwood, Robert and Liang, Xin and Wang, Bei and Di, Sheng and Cappello, Franck and Guo, Hanqi},
  journal={IEEE Transactions on Visualization and Computer Graphics},
  year={2027},
  volume={},
  number={},
  pages={},
  doi={},
  publisher={IEEE},
  note={Accepted at IEEE VIS 2026.}
}
```

---

## License & Acknowledgments

- **Source Code License**: Released under the [MIT License](./LICENSE).
- **Supplemental Materials License**: Available at <https://osf.io/7cspq> under CC BY 4.0.
- **Acknowledgments**: This work is supported by the U.S. Department of Energy, Office of Science, Advanced Scientific Computing Research (ASCR) under contract DE-AC02-06CH11357, and by the National Science Foundation under grants OAC-2311875, OAC-2311878, OAC-2514036, OAC-2514034, OAC-2609480, OAC-2513768, OAC-2313122, OAC-2313123, OAC-2313124, and OAC-2628473.
