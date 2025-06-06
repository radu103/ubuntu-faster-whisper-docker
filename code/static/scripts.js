// Store jobs globally for filtering/sorting
let allJobs = [];

// Function to render jobs in the table
function renderJobs(jobs) {
    const tableBody = document.getElementById('jobTableBody');
    tableBody.innerHTML = '';

    if (jobs.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="5" class="text-center">No jobs found</td></tr>';
        return;
    }

    jobs.forEach(job => {
        const row = document.createElement('tr');

        // Job ID (shortened)
        const idCell = document.createElement('td');
        const shortId = job.id.substring(0, 8) + '...';
        idCell.textContent = shortId;
        idCell.title = job.id;
        row.appendChild(idCell);

        // Filename
        const nameCell = document.createElement('td');
        nameCell.textContent = job.original_filename || 'Unknown file';
        row.appendChild(nameCell);

        // Status with badge
        const statusCell = document.createElement('td');
        const statusBadge = document.createElement('span');
        statusBadge.textContent = job.status;

        // Apply different badge styles based on status
        if (job.status === 'completed') {
            statusBadge.className = 'badge bg-success';
        } else if (job.status === 'processing') {
            statusBadge.className = 'badge bg-info';
        } else if (job.status === 'failed') {
            statusBadge.className = 'badge bg-danger';
        } else {
            statusBadge.className = 'badge bg-secondary';
        }

        statusCell.appendChild(statusBadge);
        row.appendChild(statusCell);

        // Created at
        const createdCell = document.createElement('td');
        createdCell.textContent = job.created_at || '';
        row.appendChild(createdCell);

        // Actions with Bootstrap buttons
        const actionCell = document.createElement('td');

        // Create button group for actions
        const btnGroup = document.createElement('div');
        btnGroup.className = 'btn-group btn-group-sm';

        // View details button
        const detailsLink = document.createElement('a');
        detailsLink.href = '/jobs/' + job.id;
        detailsLink.className = 'btn btn-info';
        detailsLink.innerHTML = '<i class="bi bi-info-circle"></i> Details';
        btnGroup.appendChild(detailsLink);

        // Download button if completed
        if (job.status === 'completed') {
            const downloadLink = document.createElement('a');
            downloadLink.href = '/download/' + job.id;
            downloadLink.className = 'btn btn-success';
            downloadLink.innerHTML = '<i class="bi bi-download"></i> Download';
            btnGroup.appendChild(downloadLink);
        }

        actionCell.appendChild(btnGroup);
        row.appendChild(actionCell);
        tableBody.appendChild(row);
    });
}

// Function to filter jobs based on input
function filterJobs() {
    const filterValue = document.getElementById('jobFilterInput').value.toLowerCase();
    const filtered = allJobs.filter(job =>
        (job.original_filename || '').toLowerCase().includes(filterValue) ||
        (job.status || '').toLowerCase().includes(filterValue) ||
        (job.id || '').toLowerCase().includes(filterValue)
    );
    renderJobs(filtered);
}

// Function to load jobs
function loadJobs() {
    fetch('/jobs')
        .then(response => response.json())
        .then(jobs => {
            // Sort jobs descending by created_at (assuming ISO string or sortable format)
            jobs.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
            allJobs = jobs;
            filterJobs();
        })
        .catch(error => {
            console.error('Error loading jobs:', error);
            const tableBody = document.getElementById('jobTableBody');
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center text-danger"><i class="bi bi-exclamation-triangle"></i> Error loading jobs</td></tr>';
        });
}

// File upload handling
function initFileUpload() {
    const uploadForm = document.getElementById('uploadForm');
    const uploadStatus = document.getElementById('uploadStatus');

    // Make sure form doesn't have action attribute that might cause redirect
    if (uploadForm.hasAttribute('action')) {
        uploadForm.removeAttribute('action');
    }

    uploadForm.addEventListener('submit', function (event) {
        // Prevent default form submission to avoid page navigation
        event.preventDefault();
        event.stopPropagation();

        const fileInput = document.getElementById('inputFile');
        if (!fileInput.files.length) {
            alert('Please select a file to upload');
            return;
        }

        const file = fileInput.files[0];
        const formData = new FormData();
        formData.append('file', file);

        // Show upload status
        uploadStatus.classList.remove('d-none');
        // Disable form during upload
        const submitButton = uploadForm.querySelector('button[type="submit"]');
        submitButton.disabled = true;

        // Upload the file using fetch API (ajax) to prevent page navigation
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                // Parse the JSON response to prevent browser from treating it as a redirect
                return response.json();
            })
            .then(data => {
                console.log('Upload response:', data);
                // Refresh jobs list
                loadJobs();

                // Hide status and reset form
                uploadStatus.classList.add('d-none');
                uploadForm.reset();
                submitButton.disabled = false;

                // Show success message
                const jobId = data && data.job_id ? data.job_id : 'Unknown';
                alert('File uploaded successfully! Job ID: ' + jobId);
            })
            .catch(error => {
                console.error('Error uploading file:', error);
                alert('Error uploading file. Please try again.');

                // Reset UI
                uploadStatus.classList.add('d-none');
                submitButton.disabled = false;
            });
    });
}

// Audio recording functionality
let mediaRecorder;
let audioChunks = [];
let recordingTimer;
let recordingSeconds = 0;
let audioBlob;

function initAudioRecording() {
    const recordButton = document.getElementById('recordButton');
    const stopButton = document.getElementById('stopButton');
    const recordingStatus = document.getElementById('recordingStatus');
    const recordingTime = document.getElementById('recordingTime');
    const audioPreview = document.getElementById('audioPreview');
    const recordedAudio = document.getElementById('recordedAudio');
    const uploadRecordingBtn = document.getElementById('uploadRecordingBtn');

    // Check if browser supports getUserMedia
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const recordTab = document.getElementById('record-tab-pane');
        recordTab.innerHTML = '<div class="alert alert-danger">Your browser does not support audio recording. Please use a modern browser like Chrome, Firefox, or Edge.</div>';
        return;
    }

    // Start recording
    recordButton.addEventListener('click', function () {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                // Show recording status
                recordingStatus.classList.remove('d-none');
                audioPreview.classList.add('d-none');

                // Update buttons
                recordButton.disabled = true;
                stopButton.disabled = false;

                // Reset timer
                recordingSeconds = 0;
                updateRecordingTime();
                recordingTimer = setInterval(updateRecordingTimer, 1000);

                // Initialize recorder
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];

                // Collect audio data
                mediaRecorder.addEventListener('dataavailable', event => {
                    audioChunks.push(event.data);
                });

                // When recording stops
                mediaRecorder.addEventListener('stop', () => {
                    // Stop all tracks in the stream
                    stream.getTracks().forEach(track => track.stop());

                    // Create audio blob
                    audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    recordedAudio.src = audioUrl;

                    // Show preview
                    audioPreview.classList.remove('d-none');
                    recordingStatus.classList.add('d-none');
                });

                // Start recording
                mediaRecorder.start();
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                recordingStatus.classList.add('d-none');
                alert('Error accessing microphone. Please ensure you have granted microphone permissions.');
                recordButton.disabled = false;
                stopButton.disabled = true;
            });
    });

    // Stop recording
    stopButton.addEventListener('click', function () {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            clearInterval(recordingTimer);
            recordButton.disabled = false;
            stopButton.disabled = true;
        }
    });

    // Upload recording
    uploadRecordingBtn.addEventListener('click', function () {
        if (!audioBlob) {
            alert('No recording available to upload');
            return;
        }

        // Create a FormData object
        const formData = new FormData();
        // Add the recording with a filename
        const filename = `recording_${new Date().toISOString().replace(/[:.]/g, '-')}.webm`;
        formData.append('file', audioBlob, filename);

        // Show loading state
        uploadRecordingBtn.disabled = true;
        uploadRecordingBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uploading...';

        // Upload the file
        fetch('/upload', {
            method: 'POST',
            body: formData
        }).then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
            .then(data => {
                console.log('Upload response:', data); // Debug log
                // Refresh jobs list
                loadJobs();

                // Reset UI
                audioPreview.classList.add('d-none');

                // Show success message with safe access to job ID
                alert('Recording uploaded successfully! Job ID: ' + data.job_id);

                // Reset button
                uploadRecordingBtn.disabled = false;
                uploadRecordingBtn.innerHTML = '<i class="bi bi-cloud-upload"></i> Upload Recording for Transcription';

                // Switch to jobs tab if we had one
                const uploadTab = document.querySelector('#upload-tab');
                if (uploadTab) {
                    uploadTab.click();
                }
            })
            .catch(error => {
                console.error('Error uploading recording:', error);
                alert('Error uploading recording. Please try again.');

                // Reset button
                uploadRecordingBtn.disabled = false;
                uploadRecordingBtn.innerHTML = '<i class="bi bi-cloud-upload"></i> Upload Recording for Transcription';
            });
    });

    function updateRecordingTimer() {
        recordingSeconds++;
        updateRecordingTime();
    }

    function updateRecordingTime() {
        const minutes = Math.floor(recordingSeconds / 60).toString().padStart(2, '0');
        const seconds = (recordingSeconds % 60).toString().padStart(2, '0');
        recordingTime.textContent = `${minutes}:${seconds}`;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    loadJobs();
    document.getElementById('jobFilterInput').addEventListener('input', filterJobs);

    // Initialize file upload handling
    initFileUpload();

    // Initialize audio recording functionality
    initAudioRecording();
});

// initialize audio recording
function initAudio() {
    if (!navigator.webkitGetUserMedia)
        return(alert("Error: getUserMedia not supported!"));

    navigator.webkitGetUserMedia({audio:true}, gotStream, function(e) {
        alert('Error getting audio');
        console.log(e);
    });
}

document.addEventListener('load', initAudio );

// Handle form submission
document.querySelector('form').addEventListener('submit', function(e) {
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    
    if (!username || !password) {
        e.preventDefault();
        errorDiv.textContent = 'Please enter both username and password';
        errorDiv.style.display = 'block';
    }
});