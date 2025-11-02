const { createApp } = Vue;

createApp({
  data() {
    return {
      jsonData: null,
      threshold: 90,
      activeChunkId: null,
      expandedChunkId: null,
      hoveredChunkId: null,
      activeSegmentIndex: null,
      isLeftScrolling: false,
      isRightScrolling: false,
      loading: false,
      error: null
    };
  },

  computed: {
    coveragePercentage() {
      if (!this.jsonData) return 0;
      return this.jsonData.metadata.coverage_percentage.toFixed(2);
    },

    totalChunks() {
      if (!this.jsonData) return 0;
      return this.jsonData.metadata.total_chunks;
    },

    significantGaps() {
      if (!this.jsonData) return 0;
      return this.jsonData.metadata.significant_gaps;
    },

    coverageMap() {
      if (!this.jsonData) return [];
      return this.jsonData.coverage_map;
    },

    filteredChunks() {
      if (!this.jsonData) return [];
      // Filter to only show chunks from the matching document
      // This handles the case where chunks directory contains chunks from multiple documents
      return this.jsonData.chunks.filter(chunk => chunk.matched);
    }
  },

  mounted() {
    // Try to auto-load JSON from data directory
    this.scanDataDirectory();

    // Load saved threshold from localStorage
    const savedThreshold = localStorage.getItem('coverageThreshold');
    if (savedThreshold) {
      this.threshold = parseInt(savedThreshold);
    }
  },

  watch: {
    threshold(newVal) {
      // Save threshold to localStorage
      localStorage.setItem('coverageThreshold', newVal);
    }
  },

  methods: {
    async scanDataDirectory() {
      // Try to auto-load the first JSON file from data directory
      const possibleFiles = [
        'data/chapter_04_coverage.json',
        'data/coverage.json',
        'data/report.json'
      ];

      for (const file of possibleFiles) {
        try {
          const response = await fetch(file);
          if (response.ok) {
            this.jsonData = await response.json();
            console.log('Auto-loaded:', file);
            return;
          }
        } catch (e) {
          // Continue to next file
        }
      }
    },

    loadJSON(event) {
      const file = event.target.files[0];
      if (!file) return;

      this.loading = true;
      this.error = null;

      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          this.jsonData = JSON.parse(e.target.result);
          this.loading = false;
          console.log('JSON loaded successfully:', this.jsonData.metadata.document_name);
        } catch (error) {
          this.error = `JSON parse error: ${error.message}`;
          this.loading = false;
          console.error('JSON parse error:', error);
        }
      };

      reader.onerror = () => {
        this.error = 'Failed to read file';
        this.loading = false;
      };

      reader.readAsText(file);
    },

    onChunkClick(chunk) {
      this.activeChunkId = chunk.chunk_id;

      // Find the segment in coverage map
      const segmentIndex = this.coverageMap.findIndex(
        seg => seg.type === 'covered' && seg.chunk_id === chunk.chunk_id
      );

      if (segmentIndex !== -1) {
        this.activeSegmentIndex = segmentIndex;
        this.scrollToSegment(segmentIndex);
      }
    },

    onChunkHover(chunk) {
      this.hoveredChunkId = chunk.chunk_id;
    },

    onChunkLeave() {
      this.hoveredChunkId = null;
    },

    onSegmentClick(segment, index) {
      this.activeSegmentIndex = index;

      // If segment is covered, activate the corresponding chunk
      if (segment.type === 'covered' && segment.chunk_id) {
        this.activeChunkId = segment.chunk_id;

        // Scroll to the chunk in right panel
        this.$nextTick(() => {
          const chunkElement = document.querySelector(
            `.chunk-card[data-chunk-id="${segment.chunk_id}"]`
          );
          if (chunkElement) {
            chunkElement.scrollIntoView({
              behavior: 'smooth',
              block: 'center'
            });
          }
        });
      }
    },

    toggleExpanded(chunkId) {
      if (this.expandedChunkId === chunkId) {
        this.expandedChunkId = null;
      } else {
        this.expandedChunkId = chunkId;
      }
    },

    getSegmentClass(segment) {
      if (segment.type === 'gap') {
        return segment.length <= 5 ? 'segment-small-gap' : 'segment-gap';
      }

      // Covered segment - classify by similarity and threshold
      const thresholdValue = this.threshold / 100;
      const similarity = segment.similarity;

      if (similarity >= 0.95) {
        return 'segment-high';
      } else if (similarity >= 0.90) {
        return 'segment-medium';
      } else if (similarity >= thresholdValue) {
        return 'segment-low';
      } else {
        // Below threshold - treat as gap
        return 'segment-gap';
      }
    },

    getSimilarityClass(similarity) {
      if (similarity >= 0.95) return 'similarity-high';
      if (similarity >= 0.90) return 'similarity-medium';
      return 'similarity-low';
    },

    getCoverageClass() {
      const coverage = parseFloat(this.coveragePercentage);
      if (coverage >= 95) return 'coverage-high';
      if (coverage >= 80) return 'coverage-medium';
      return 'coverage-low';
    },

    getSegmentText(segment) {
      if (!this.jsonData) return '';
      return this.jsonData.original_text.substring(segment.start, segment.end);
    },

    getSegmentTitle(segment) {
      if (segment.type === 'gap') {
        return `Gap: ${segment.length} characters`;
      }
      return `Chunk: ${segment.chunk_id} (${(segment.similarity * 100).toFixed(1)}% similarity)`;
    },

    scrollToSegment(segmentIndex) {
      this.$nextTick(() => {
        const segments = this.$refs.leftPanel.querySelectorAll('.segment');
        if (segments[segmentIndex]) {
          segments[segmentIndex].scrollIntoView({
            behavior: 'smooth',
            block: 'center'
          });
        }
      });
    },

    onLeftScroll() {
      if (this.isRightScrolling) return;

      this.isLeftScrolling = true;

      // Debounce scroll handling
      clearTimeout(this.leftScrollTimeout);
      this.leftScrollTimeout = setTimeout(() => {
        this.isLeftScrolling = false;
      }, 100);
    },

    onRightScroll() {
      if (this.isLeftScrolling) return;

      this.isRightScrolling = true;

      // Debounce scroll handling
      clearTimeout(this.rightScrollTimeout);
      this.rightScrollTimeout = setTimeout(() => {
        this.isRightScrolling = false;
      }, 100);
    }
  }
}).mount('#app');
