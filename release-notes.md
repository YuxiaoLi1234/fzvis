## Version 0.3.0
### New Features
#### Dashboard Redesign
- Separated configuration panels (datasets and compressors) from visualization panels (spatial data and metrics) for improved workflow clarity.
- Implemented responsive user interface using the [Bootstrap](https://getbootstrap.com/) framework.
- Placed project information to a dedicated off-canvas panel.
- Added a direct link to the GitHub repository in the page header.
- Positioned the AI assistant in the bottom-right corner of the webpage.

#### Input Dataset Management
- Enabled direct dataset upload, storage, and management on the remote server via the frontend interface.
- Added dataset switching without requiring compressor redesign.
- Implemented NetCDF file format support, featuring:
  - Tabular display of variables and dimensionality.
  - Variable selection and data slicing for compressor configuration.

#### Compressor Configuration
- Added support for configuring the SZ3 compressor.
- Implemented the display of documentation for compressor options by hovering over the input field.
- Introduced error bound propagation for batch configuration generation.
- Enabled individual error bound modification and removal.

#### Spatial Data Visualization
- Integrated [vtk.js](https://kitware.github.io/vtk-js/index.html) for high-performance visualization of large datasets.
- Added support for both 2D image and 3D volume visualization.
- Implemented full built-in vtk.js colormap support.
- Enabled synchronized camera views and colormap ranges across multiple data visualizations.
- Added time-series data visualization for NetCDF files with global/local/custom range options.

#### Metrics Visualization
- Implemented multiple metrics selection and comparison for configured compressors.
- Improved bar chart spacing to prevent overlap.
- Added scrollable legend area for better multi-compressor comparison.

#### AI Assistant
- Integrated Large Language Model (LLM) for lossy compressor queries. 


## Version 0.2.4
Dist directory path fix


## Version 0.2.3
Minor bug fix with slice visualization.


## Version 0.2.1
### New Features and Improvements

#### Dynamic IP Configuration
- Removed all hard-coded IP addresses and URLs.
- Backend dynamically determines the environment, ensuring better portability and user convenience.

#### Unified Port Setup
- Simplified port usage by hosting both the backend and frontend through a single Flask server running on port 5001.
- No need for a separate server or additional configurations for the frontend on port 8080.

#### Streamlined Execution
- The entire application can now be started with a single command: running the main.py file.

#### Improved Static Content Hosting
- Integrated static file hosting with Flask to serve frontend files (HTML, JavaScript, and CSS) directly.

#### Fixes for Slice Visualization for 3D Datasets
- Resolved issues with slice visualization for 3D datasets.

### How to Use

- Install the project or clone the repository: `spack install fzvis`
- Run the single executable: `./fzvis`
- Access the application at http://localhost:5001.


## Version 0.2.1
### Bug Fixes

#### WebSocket Connection Stability
- Fixed intermittent connection issues between frontend and backend, ensuring a more reliable WebSocket connection.
- Improved handling of WebSocket URL configuration, allowing easier setup for different environments and dynamic IPs.

#### Cross-Origin Communication
- Resolved CORS-related issues affecting WebSocket requests, ensuring compatibility when running frontend and backend on different origins.


## Version 0.2.0

### New Features and Improvements

#### Enhanced Comparative Analysis
- Improved visualization for comparing metrics across multiple compressors.
- Added error-bound configuration and metric category selection for better analysis.

#### Dashboard Redesign
- Simplified and more interactive user interface for easier navigation.
- Optimized configuration saving and submission process.

#### Input Dataset Management
- Updated input dataset upload functionality with precision and dimension settings.
- Binary input dataset format is now supported for enhanced flexibility.
- Enhanced slice visualization module with custom colormap options and interactive control points.


## Version 0.1.0

### Major Modules
- Comparative visual analysis of lossy compressor metrics results.
- Slice visualization of input datasets.
- Enabled user interactions.
