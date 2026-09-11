const REPORT_WIDTH = 976;
const PRINT_SCALE = (186 / 25.4 * 96) / REPORT_WIDTH;

export const PDF_PRINT_STYLES = `
      @page { size: A4; margin: 12mm; }
      html, body { margin: 0 !important; padding: 0 !important; }
      body { min-height: 0 !important; overflow: visible !important; }
      #print-report { width: ${REPORT_WIDTH}px; }
      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
        -webkit-print-color-adjust: exact !important;
        print-color-adjust: exact !important;
      }
      @media print {
        #print-report { zoom: ${PRINT_SCALE}; }
        [data-pdf-keep] { break-inside: avoid; }
        [data-pdf-heading] { break-after: avoid; }
        details, li, [data-pdf-heading] + div { overflow: visible !important; }
        /* Gradient text is rasterized by some print engines. Keep the title text. */
        .text-gradient-brand {
          background: none !important;
          color: hsl(var(--brand-700)) !important;
          -webkit-text-fill-color: currentColor !important;
        }
      }
    `;
