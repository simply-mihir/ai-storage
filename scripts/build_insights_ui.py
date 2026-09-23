"""Script to inject Insights tab UI, Plotly script, styling, and pre-serialized figures into static/index.html and index.html."""
import json
from pathlib import Path
from storage_advisor.analytics.insights import all_figures, get_family_catalog

def build():
    dark_figs = {k: json.loads(v) for k, v in all_figures(dark=True).items()}
    light_figs = {k: json.loads(v) for k, v in all_figures(dark=False).items()}
    catalog = get_family_catalog()

    cache_data = {
        "dark": dark_figs,
        "light": light_figs,
        "catalog": catalog,
    }
    cache_json = json.dumps(cache_data, separators=(',', ':'))

    plotly_script = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'
    tab_button = '<button class="tab-pill-btn" role="tab" id="tab-btn-insights" aria-selected="false" aria-controls="panel-insights">Insights</button>'

    insights_css = """
    /* ==========================================================================
       INSIGHTS TAB (PLOTLY FIGURES & NETWORK GRAPH)
       ========================================================================== */
    .insights-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 24px;
      margin-bottom: 24px;
    }
    @media (max-width: 1024px) {
      .insights-grid {
        grid-template-columns: 1fr;
      }
    }
    .insights-card {
      border-radius: var(--radius-card);
      padding: 24px;
      display: flex;
      flex-direction: column;
    }
    .insights-card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
      flex-wrap: wrap;
      gap: 8px;
    }
    .insights-card-title {
      font-size: 1.15rem;
      color: var(--text);
      font-family: var(--font-display);
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .insights-card-sub {
      font-size: 0.8rem;
      color: var(--text2);
      margin-top: 2px;
    }
    .insights-plot-well {
      border-radius: var(--radius-card);
      padding: 12px;
      height: 450px;
      min-height: 450px;
      position: relative;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      background: var(--well);
      box-shadow: var(--shadow-inset);
    }
    .insights-plot-container {
      width: 100%;
      height: 100%;
      min-height: 426px;
    }
    .insights-graph-layout {
      display: grid;
      grid-template-columns: 1fr 340px;
      gap: 20px;
      margin-top: 12px;
    }
    @media (max-width: 1100px) {
      .insights-graph-layout {
        grid-template-columns: 1fr;
      }
    }
    .insights-graph-well {
      border-radius: var(--radius-card);
      padding: 12px;
      height: 520px;
      min-height: 520px;
      background: var(--well);
      box-shadow: var(--shadow-inset);
    }
    .insights-detail-drawer {
      border-radius: var(--radius-card);
      padding: 20px;
      background: var(--well);
      box-shadow: var(--shadow-inset);
      display: flex;
      flex-direction: column;
      max-height: 544px;
      overflow-y: auto;
    }
    .drawer-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      margin-bottom: 12px;
    }
    .drawer-tag {
      font-size: 0.7rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: var(--radius-pill);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .variant-item-pill {
      border-radius: var(--radius-input);
      background: var(--surface);
      box-shadow: var(--shadow-raised-sm);
      padding: 10px 12px;
      margin-top: 8px;
      border-left: 3px solid var(--accent);
    }
"""

    panel_html = """
      <!-- ====================================================================
           TAB 8: INSIGHTS
           ==================================================================== -->
      <section class="dash-tab-panel" id="panel-insights" role="tabpanel" aria-labelledby="tab-btn-insights">
        <!-- Stat strip for insights -->
        <div class="stat-strip" style="margin-bottom: 24px; padding: 0;">
          <div class="stat-strip-well">
            <div class="tabular stat-strip-num gradient-text">2,000</div>
            <div class="stat-strip-label">Scenarios Synthesized</div>
          </div>
          <div class="stat-strip-well">
            <div class="tabular stat-strip-num gradient-text">26</div>
            <div class="stat-strip-label">Technique Families</div>
          </div>
          <div class="stat-strip-well">
            <div class="tabular stat-strip-num gradient-text">39</div>
            <div class="stat-strip-label">Synergies &amp; Conflicts</div>
          </div>
          <div class="stat-strip-well">
            <div class="tabular stat-strip-num gradient-text">DuckDB</div>
            <div class="stat-strip-label">Analytics Engine</div>
          </div>
        </div>

        <!-- 2x2 Grid of Inset Wells hosting Plotly Figures -->
        <div class="insights-grid">
          <!-- Card 1: Treemap -->
          <div class="insights-card neu-raised">
            <div class="insights-card-header">
              <div>
                <h3 class="insights-card-title">Technique Recommendation Frequency</h3>
                <div class="insights-card-sub">Hierarchical volume distribution across 2,000 scenarios</div>
              </div>
              <span class="fx-chip"><span class="fx-chip-led live"></span><span>Treemap</span></span>
            </div>
            <div class="insights-plot-well neu-inset">
              <div id="plot-treemap" class="insights-plot-container"></div>
            </div>
          </div>

          <!-- Card 2: Industry Savings Heatmap -->
          <div class="insights-card neu-raised">
            <div class="insights-card-header">
              <div>
                <h3 class="insights-card-title">Industry × Avg Storage Savings</h3>
                <div class="insights-card-sub">Cross-tabulation of savings magnitude by business domain</div>
              </div>
              <span class="fx-chip"><span class="fx-chip-led live"></span><span>Heatmap</span></span>
            </div>
            <div class="insights-plot-well neu-inset">
              <div id="plot-industry-heatmap" class="insights-plot-container"></div>
            </div>
          </div>

          <!-- Card 3: Correlation Matrix -->
          <div class="insights-card neu-raised">
            <div class="insights-card-header">
              <div>
                <h3 class="insights-card-title">Feature Correlation Matrix</h3>
                <div class="insights-card-sub">Pearson correlation: workload scale vs savings targets</div>
              </div>
              <span class="fx-chip"><span class="fx-chip-led live"></span><span>Correlation</span></span>
            </div>
            <div class="insights-plot-well neu-inset">
              <div id="plot-correlation" class="insights-plot-container"></div>
            </div>
          </div>

          <!-- Card 4: Bubble Chart -->
          <div class="insights-card neu-raised">
            <div class="insights-card-header">
              <div>
                <h3 class="insights-card-title">Workload Growth vs Storage Savings</h3>
                <div class="insights-card-sub">X: Daily growth GB · Y: Savings % · Bubble size: Users · Color: Domain</div>
              </div>
              <span class="fx-chip"><span class="fx-chip-led live"></span><span>Bubble Scatter</span></span>
            </div>
            <div class="insights-plot-well neu-inset">
              <div id="plot-bubble" class="insights-plot-container"></div>
            </div>
          </div>
        </div>

        <!-- Full Width: Technique Relationship Graph + Inset Detail Drawer -->
        <div class="insights-card neu-raised" style="margin-bottom: 24px;">
          <div class="insights-card-header">
            <div>
              <h3 class="insights-card-title">Technique Relationship Network &amp; Architecture Graph</h3>
              <div class="insights-card-sub">NetworkX spring layout: Nodes colored by category · Teal = Synergy · Red = Conflict · Dashed = Requires</div>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
              <span class="fx-chip" style="color: var(--teal);"><span class="fx-chip-led live" style="background: var(--teal);"></span><span>Synergy</span></span>
              <span class="fx-chip" style="color: var(--neg);"><span class="fx-chip-led live" style="background: var(--neg);"></span><span>Conflict</span></span>
              <span class="fx-chip" style="color: var(--text2);"><span class="fx-chip-led default"></span><span>Requires</span></span>
            </div>
          </div>

          <div class="insights-graph-layout">
            <div class="insights-graph-well neu-inset">
              <div id="plot-technique-graph" style="width: 100%; height: 500px;"></div>
            </div>

            <!-- Inset Detail Drawer (Node Click) -->
            <div class="insights-detail-drawer" id="technique-detail-drawer">
              <div id="drawer-empty-state" style="margin: auto; text-align: center; color: var(--text3); padding: 20px;">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: 8px; opacity: 0.6;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
                <div style="font-size: 0.95rem; font-weight: 600; color: var(--text2);">Select a Technique Node</div>
                <p style="font-size: 0.8rem; margin-top: 6px; line-height: 1.4;">Click any node in the relationship network to inspect family metadata, architectural mechanisms, and available variants.</p>
              </div>

              <div id="drawer-content" style="display: none;">
                <div class="drawer-header">
                  <div>
                    <span class="drawer-tag" id="drawer-category-tag" style="background: rgba(249,115,22,0.15); color: var(--accent);">Category</span>
                    <h4 id="drawer-title" style="font-size: 1.25rem; font-family: var(--font-display); color: var(--text); margin-top: 4px;">Technique Name</h4>
                    <span id="drawer-id" style="font-size: 0.75rem; color: var(--text3); font-family: monospace;">family_id</span>
                  </div>
                  <button class="circle-btn" id="drawer-close-btn" aria-label="Close details" style="width: 28px; height: 28px; min-width: 28px;">
                    <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
                  </button>
                </div>

                <div style="margin-top: 8px;">
                  <div style="font-size: 0.72rem; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Summary</div>
                  <p id="drawer-summary" style="font-size: 0.85rem; color: var(--text2); line-height: 1.5; margin-bottom: 12px;"></p>

                  <div id="drawer-mechanism-box" style="margin-bottom: 12px;">
                    <div style="font-size: 0.72rem; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Mechanism</div>
                    <p id="drawer-mechanism" style="font-size: 0.82rem; color: var(--text2); line-height: 1.4; background: var(--surface2); padding: 8px 10px; border-radius: var(--radius-input);"></p>
                  </div>

                  <div id="drawer-solves-box" style="margin-bottom: 12px;">
                    <div style="font-size: 0.72rem; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px;">Problems Solved</div>
                    <div id="drawer-solves-chips" style="display: flex; flex-wrap: wrap; gap: 4px;"></div>
                  </div>

                  <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                      <div style="font-size: 0.72rem; font-weight: 700; color: var(--text3); text-transform: uppercase; letter-spacing: 0.05em;">Variants (<span id="drawer-variant-count">0</span>)</div>
                    </div>
                    <div id="drawer-variants-list"></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>
"""

    insights_js = """
      /* ----------------------------------------------------------------------
         INSIGHTS TAB LOGIC & THEME-AWARE PLOTLY INTEGRATION
         ---------------------------------------------------------------------- */
      let insightsData = null;
      window.insightsRendered = false;

      function getInsightsCache() {
        if (!insightsData) {
          const el = document.getElementById('insights-figures-data');
          if (el) {
            try {
              insightsData = JSON.parse(el.textContent);
            } catch(e) {
              console.warn('Failed to parse embedded insights data', e);
            }
          }
        }
        return insightsData;
      }

      function getThemePalette() {
        const isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        const styles = getComputedStyle(document.documentElement);
        return {
          isDark,
          text: styles.getPropertyValue('--text').trim() || (isDark ? '#F5F5F5' : '#16181D'),
          text2: styles.getPropertyValue('--text2').trim() || (isDark ? '#A0A0A0' : '#5C6470'),
          text3: styles.getPropertyValue('--text3').trim() || (isDark ? '#6B6B6B' : '#8B93A1'),
          accent: styles.getPropertyValue('--accent').trim() || (isDark ? '#F97316' : '#EA580C'),
          teal: styles.getPropertyValue('--teal').trim() || (isDark ? '#14B8A6' : '#0D9488'),
          grid: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
          well: styles.getPropertyValue('--well').trim() || (isDark ? '#101010' : '#D5DAE2'),
          surface: styles.getPropertyValue('--surface').trim() || (isDark ? '#1B1B1B' : '#E9EDF2'),
        };
      }

      function renderInsights() {
        if (typeof Plotly === 'undefined') {
          console.warn('Plotly not loaded yet');
          return;
        }
        const data = getInsightsCache();
        if (!data) return;

        const palette = getThemePalette();
        const mode = palette.isDark ? 'dark' : 'light';
        const specs = data[mode];
        if (!specs) return;

        const plotConfigs = { responsive: true, displayModeBar: false };

        const themeLayout = (layout) => {
          const l = { ...layout };
          l.paper_bgcolor = 'rgba(0,0,0,0)';
          l.plot_bgcolor = 'rgba(0,0,0,0)';
          l.font = { ...(l.font || {}), color: palette.text, family: 'Inter, sans-serif' };
          if (l.title) {
            l.title = typeof l.title === 'string'
              ? { text: l.title, font: { color: palette.text, family: 'Space Grotesk, sans-serif', size: 14 } }
              : { ...l.title, font: { color: palette.text, family: 'Space Grotesk, sans-serif', size: 14 } };
          }
          if (l.xaxis) {
            l.xaxis = { ...l.xaxis, tickfont: { color: palette.text2 }, gridcolor: palette.grid };
            if (l.xaxis.title) {
              l.xaxis.title = typeof l.xaxis.title === 'string'
                ? { text: l.xaxis.title, font: { color: palette.text } }
                : { ...l.xaxis.title, font: { color: palette.text } };
            }
          }
          if (l.yaxis) {
            l.yaxis = { ...l.yaxis, tickfont: { color: palette.text2 }, gridcolor: palette.grid };
            if (l.yaxis.title) {
              l.yaxis.title = typeof l.yaxis.title === 'string'
                ? { text: l.yaxis.title, font: { color: palette.text } }
                : { ...l.yaxis.title, font: { color: palette.text } };
            }
          }
          l.autosize = true;
          return l;
        };

        // 1. Treemap
        if (specs.treemap && document.getElementById('plot-treemap')) {
          Plotly.react('plot-treemap', specs.treemap.data, themeLayout(specs.treemap.layout), plotConfigs);
        }

        // 2. Industry Savings Heatmap
        if (specs.industry_heatmap && document.getElementById('plot-industry-heatmap')) {
          Plotly.react('plot-industry-heatmap', specs.industry_heatmap.data, themeLayout(specs.industry_heatmap.layout), plotConfigs);
        }

        // 3. Correlation Matrix
        if (specs.correlation && document.getElementById('plot-correlation')) {
          Plotly.react('plot-correlation', specs.correlation.data, themeLayout(specs.correlation.layout), plotConfigs);
        }

        // 4. Bubble Growth vs Savings
        if (specs.bubble && document.getElementById('plot-bubble')) {
          Plotly.react('plot-bubble', specs.bubble.data, themeLayout(specs.bubble.layout), plotConfigs);
        }

        // 5. Technique Relationship Graph
        const graphEl = document.getElementById('plot-technique-graph');
        if (specs.graph && graphEl) {
          Plotly.react('plot-technique-graph', specs.graph.data, themeLayout(specs.graph.layout), plotConfigs);
          if (!graphEl._hasClickListener) {
            graphEl.on('plotly_click', function(evtData) {
              if (!evtData || !evtData.points || !evtData.points.length) return;
              const pt = evtData.points[0];
              const famId = pt.customdata || pt.text;
              if (famId) {
                showFamilyDetail(famId);
              }
            });
            graphEl._hasClickListener = true;
          }
        }

        window.insightsRendered = true;
      }

      function showFamilyDetail(familyId) {
        const data = getInsightsCache();
        if (!data || !data.catalog) return;
        const fam = data.catalog[familyId];
        if (!fam) return;

        const emptyState = document.getElementById('drawer-empty-state');
        const content = document.getElementById('drawer-content');
        if (emptyState) emptyState.style.display = 'none';
        if (content) content.style.display = 'block';

        const titleEl = document.getElementById('drawer-title');
        const idEl = document.getElementById('drawer-id');
        const catTagEl = document.getElementById('drawer-category-tag');
        const summaryEl = document.getElementById('drawer-summary');
        const mechEl = document.getElementById('drawer-mechanism');
        const mechBox = document.getElementById('drawer-mechanism-box');
        const solvesChips = document.getElementById('drawer-solves-chips');
        const varCountEl = document.getElementById('drawer-variant-count');
        const varListEl = document.getElementById('drawer-variants-list');

        if (titleEl) titleEl.textContent = fam.name;
        if (idEl) idEl.textContent = fam.id;
        if (catTagEl) {
          catTagEl.textContent = fam.category;
          const catColors = {
            analytics: '#F97316', architecture: '#14B8A6', caching: '#FBBF24',
            database: '#3B82F6', infrastructure: '#8B5CF6', networking: '#EC4899',
            reliability: '#10B981', security: '#EF4444', storage: '#6366F1'
          };
          const c = catColors[fam.category] || 'var(--accent)';
          catTagEl.style.color = c;
          catTagEl.style.background = c + '22';
        }
        if (summaryEl) summaryEl.textContent = fam.summary;
        if (mechEl && mechBox) {
          if (fam.mechanism) {
            mechEl.textContent = fam.mechanism;
            mechBox.style.display = 'block';
          } else {
            mechBox.style.display = 'none';
          }
        }

        if (solvesChips) {
          if (fam.solves && fam.solves.length) {
            solvesChips.innerHTML = fam.solves.map(p =>
              `<span class="pill" style="font-size: 0.7rem; padding: 2px 8px; background: var(--surface2); color: var(--text); border: 1px solid var(--border);">${p}</span>`
            ).join('');
            document.getElementById('drawer-solves-box').style.display = 'block';
          } else {
            document.getElementById('drawer-solves-box').style.display = 'none';
          }
        }

        const variants = fam.variants || [];
        if (varCountEl) varCountEl.textContent = variants.length;
        if (varListEl) {
          if (variants.length > 0) {
            varListEl.innerHTML = variants.map(v => `
              <div class="variant-item-pill">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2px;">
                  <strong style="font-size: 0.82rem; color: var(--text);">${v.name}</strong>
                  <span class="delta-pill delta-green" style="font-size: 0.65rem; padding: 1px 6px;">${v.complexity || 'STANDARD'}</span>
                </div>
                <div style="font-size: 0.72rem; color: var(--text3); font-family: monospace;">${v.id}</div>
                ${v.summary ? `<p style="font-size: 0.76rem; color: var(--text2); margin-top: 4px; line-height: 1.35;">${v.summary}</p>` : ''}
              </div>
            `).join('');
          } else {
            varListEl.innerHTML = '<div style="font-size: 0.8rem; color: var(--text3); font-style: italic; padding: 8px 0;">Core standalone technique without variants.</div>';
          }
        }
      }

      function resetFamilyDrawer() {
        const emptyState = document.getElementById('drawer-empty-state');
        const content = document.getElementById('drawer-content');
        if (emptyState) emptyState.style.display = 'block';
        if (content) content.style.display = 'none';
      }

      document.getElementById('drawer-close-btn')?.addEventListener('click', resetFamilyDrawer);

      function resizePlotlyCharts() {
        const ids = ['plot-treemap', 'plot-industry-heatmap', 'plot-correlation', 'plot-bubble', 'plot-technique-graph'];
        ids.forEach(id => {
          const el = document.getElementById(id);
          if (el && typeof Plotly !== 'undefined') {
            try { Plotly.Plots.resize(el); } catch(e) {}
          }
        });
      }

      function initInsightsTab() {
        renderInsights();
        // Also optionally refresh from live API in background if available
        fetch(`/api/v1/insights?dark=${document.documentElement.getAttribute('data-theme') !== 'light'}`)
          .then(r => r.ok ? r.json() : null)
          .then(live => {
            if (live && live.figures) {
              const data = getInsightsCache() || { dark: {}, light: {}, catalog: {} };
              const mode = document.documentElement.getAttribute('data-theme') !== 'light' ? 'dark' : 'light';
              data[mode] = {
                treemap: JSON.parse(live.figures.treemap),
                industry_heatmap: JSON.parse(live.figures.industry_heatmap),
                correlation: JSON.parse(live.figures.correlation),
                bubble: JSON.parse(live.figures.bubble),
                graph: JSON.parse(live.figures.graph),
              };
              if (live.catalog) data.catalog = live.catalog;
              insightsData = data;
              renderInsights();
            }
          })
          .catch(() => { /* silent fallback to baked cache */ });
      }

      window.addEventListener('resize', () => {
        if (state.activeTab === 'insights') {
          resizePlotlyCharts();
        }
      });

      // Expose globally
      window.renderInsights = renderInsights;
      window.initInsightsTab = initInsightsTab;
      window.showFamilyDetail = showFamilyDetail;
      window.resizePlotlyCharts = resizePlotlyCharts;
"""

    for target_path in ["static/index.html", "index.html"]:
        p = Path(target_path)
        if not p.exists():
            continue
        content = p.read_text(encoding="utf-8")

        # 1. Add Plotly CDN
        if "plotly-2.35.2.min.js" not in content:
            content = content.replace("<!-- Permitted CDNs -->", f"<!-- Permitted CDNs -->\n  {plotly_script}")

        # 2. Add insights CSS
        marker = "/* ==========================================================================\n       1. TOKENS & NEUMORPHIC GRAMMAR"
        if "INSIGHTS TAB (PLOTLY FIGURES & NETWORK GRAPH)" not in content and marker in content:
            content = content.replace(marker, f"{insights_css}\n\n    {marker}")

        # 3. Add tab button
        whatif_btn = '<button class="tab-pill-btn" role="tab" id="tab-btn-what-if" aria-selected="false" aria-controls="panel-what-if">What-If</button>'
        if 'id="tab-btn-insights"' not in content and whatif_btn in content:
            content = content.replace(
                whatif_btn,
                f"{whatif_btn}\n          {tab_button}"
            )

        # 4. Add panel-insights section
        if 'id="panel-insights"' not in content:
            whatif_end = content.find('id="panel-what-if"')
            if whatif_end != -1:
                section_end = content.find('</section>', whatif_end)
                if section_end != -1:
                    insert_pos = section_end + len('</section>')
                    content = content[:insert_pos] + panel_html + content[insert_pos:]

        # 5. Update tabs array
        content = content.replace(
            "const tabs = ['architect', 'recommendations', 'impact', 'real-cost', 'explainability', 'growth', 'what-if'];",
            "const tabs = ['architect', 'recommendations', 'impact', 'real-cost', 'explainability', 'growth', 'what-if', 'insights'];"
        )

        # 6. Hook switchTab for insights
        growth_line = "if (tabId === 'growth' && charts.growthChart) charts.growthChart.resize();"
        if "if (tabId === 'insights')" not in content and growth_line in content:
            content = content.replace(
                growth_line,
                growth_line + "\n          if (tabId === 'insights') { initInsightsTab(); setTimeout(resizePlotlyCharts, 60); }"
            )

        # 7. Hook toggleTheme for insights
        toggle_orig = "function toggleTheme() {\n        state.theme = state.theme === 'dark' ? 'light' : 'dark';\n        document.documentElement.setAttribute('data-theme', state.theme);\n        localStorage.setItem('theme', state.theme);\n        restyleCharts();\n      }"
        toggle_new = "function toggleTheme() {\n        state.theme = state.theme === 'dark' ? 'light' : 'dark';\n        document.documentElement.setAttribute('data-theme', state.theme);\n        localStorage.setItem('theme', state.theme);\n        restyleCharts();\n        if (window.insightsRendered) { renderInsights(); }\n      }"
        if "if (window.insightsRendered)" not in content and toggle_orig in content:
            content = content.replace(toggle_orig, toggle_new)

        # 8. Add cache JSON and insights JS
        if 'id="insights-figures-data"' not in content:
            cache_tag = f'<script id="insights-figures-data" type="application/json">{cache_json}</script>'
            script_idx = content.find('<script>')
            if script_idx != -1:
                content = content[:script_idx] + f"{cache_tag}\n  " + content[script_idx:]

        if "INSIGHTS TAB LOGIC & THEME-AWARE PLOTLY INTEGRATION" not in content:
            last_close = content.rfind('})();')
            if last_close != -1:
                content = content[:last_close] + insights_js + "\n    " + content[last_close:]

        p.write_text(content, encoding="utf-8")
        print(f"Updated {target_path} successfully (size: {len(content)} bytes)")

if __name__ == "__main__":
    build()
