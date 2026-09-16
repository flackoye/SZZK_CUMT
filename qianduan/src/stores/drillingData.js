import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getPreviewBootstrap } from '../api/inference'

const dataUrl = (fileName) => `${import.meta.env.BASE_URL}data/${fileName}`

export const useDrillingStore = defineStore('drillingData', () => {
  // ---- state ----
  const summary = ref(null)
  const experiments = ref([])
  const overallMetrics = ref([])
  const byFileMetrics = ref([])
  const telemetry = ref(null)
  const ringCloud = ref(null)
  const spatialRoadway = ref(null)
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref(null)
  const previewSource = ref(null)

  const selectedStress = ref(20)
  const selectedModel = ref('v3')
  const selectedBoreholeId = ref('BH-01')
  const selectedExperimentId = ref(null)

  const activeRun = ref(null)
  const isDynamic = ref(false)
  const analysisResult = ref(null)
  const dynamicKpis = ref(null)

  // ---- actions ----
  async function loadSummary() {
    if (loaded.value || loading.value) return
    loading.value = true
    try {
      const resp = await fetch(dataUrl('dashboard_summary.json'))
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      summary.value = await resp.json()
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  async function loadExperimentManifest() {
    if (experiments.value.length > 0) return
    try {
      const resp = await fetch(dataUrl('experiment_manifest.csv'))
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const text = await resp.text()
      experiments.value = parseCSV(text)
    } catch (err) {
      console.warn('Failed to load experiment manifest:', err.message)
    }
  }

  async function loadMetrics() {
    if (overallMetrics.value.length > 0) return
    try {
      const [overallResp, byFileResp] = await Promise.all([
        fetch(dataUrl('overall_metrics.csv')),
        fetch(dataUrl('by_file_metrics.csv'))
      ])
      if (overallResp.ok) {
        const text = await overallResp.text()
        overallMetrics.value = parseCSV(text)
      }
      if (byFileResp.ok) {
        const text = await byFileResp.text()
        byFileMetrics.value = parseCSV(text)
      }
    } catch (err) {
      console.warn('Failed to load metrics:', err.message)
    }
  }

  async function loadTelemetry() {
    if (telemetry.value) return
    try {
      const resp = await fetch(dataUrl('drilling_telemetry.json'))
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      telemetry.value = await resp.json()
    } catch (err) {
      error.value = `遥测数据加载失败：${err.message}`
    }
  }

  async function loadRingCloud() {
    if (ringCloud.value) return
    try {
      const resp = await fetch(dataUrl('ring_cloud_v4.json'))
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      ringCloud.value = await resp.json()
      if (!ringCloud.value.boreholes?.some(item => item.id === selectedBoreholeId.value)) {
        selectedBoreholeId.value = ringCloud.value.boreholes?.[0]?.id || null
      }
    } catch (err) {
      error.value = `Vtest4 环形钻孔数据加载失败：${err.message}`
    }
  }

  async function loadSpatialRoadway() {
    if (spatialRoadway.value) return
    try {
      const resp = await fetch(dataUrl('roadway_spatial_v4.json'))
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      spatialRoadway.value = await resp.json()
    } catch (err) {
      error.value = `巷道空间反演数据加载失败：${err.message}`
    }
  }

  async function loadAll() {
    if (loaded.value) return
    try {
      const bundle = await getPreviewBootstrap()
      if (!bundle?.summary || !bundle?.ringCloud || !bundle?.spatialRoadway) {
        throw new Error('后端返回的预览基准数据不完整')
      }
      summary.value = bundle.summary
      ringCloud.value = bundle.ringCloud
      spatialRoadway.value = bundle.spatialRoadway
      previewSource.value = bundle.source || 'backend'
      error.value = null
      if (!ringCloud.value.boreholes?.some(item => item.id === selectedBoreholeId.value)) {
        selectedBoreholeId.value = ringCloud.value.boreholes?.[0]?.id || null
      }
    } catch (err) {
      // Keep the page inspectable when the backend has not been started yet, but
      // record that this is a static fallback rather than the intended API path.
      console.warn('Backend preview bootstrap failed, using static fallback:', err.message)
      previewSource.value = 'static-fallback'
      await Promise.all([loadSummary(), loadRingCloud(), loadSpatialRoadway()])
    }
    loaded.value = true
  }

  function parseCSV(text) {
    const lines = text.trim().split('\n')
    if (lines.length < 2) return []
    const headers = lines[0].split(',').map(h => h.trim())
    return lines.slice(1).map(line => {
      const values = line.split(',')
      const obj = {}
      headers.forEach((h, i) => {
        const v = values[i]?.trim()
        obj[h] = isNaN(v) || v === '' ? v : parseFloat(v)
      })
      return obj
    })
  }

  // ---- computed ----
  const activeModel = computed(() => {
    const v4Model = ringCloud.value?.meta?.models?.find(m => m.id === selectedModel.value)
    if (v4Model) {
      return {
        id: v4Model.id,
        name: v4Model.name,
        name_en: v4Model.nameEn,
        damage_accuracy: v4Model.damageAccuracy,
        stress_accuracy: v4Model.stressAccuracy,
        state_accuracy: v4Model.stateAccuracy,
        macro_f1: v4Model.macroF1,
        confidence: v4Model.confidence
      }
    }
    if (!summary.value) return null
    return summary.value.models.find(m => m.id === selectedModel.value) || summary.value.models[0]
  })

  const models = computed(() => (ringCloud.value?.meta?.models || []).map(model => ({
    id: model.id,
    name: model.name,
    name_en: model.nameEn,
    damage_accuracy: model.damageAccuracy,
    stress_accuracy: model.stressAccuracy,
    state_accuracy: model.stateAccuracy,
    macro_f1: model.macroF1,
    confidence: model.confidence
  })))

  const boreholes = computed(() => ringCloud.value?.boreholes || [])
  const activeBorehole = computed(() => (
    boreholes.value.find(item => item.id === selectedBoreholeId.value) || boreholes.value[0] || null
  ))

  const stressLevels = computed(() => {
    if (!summary.value) return []
    return summary.value.dataset.stress_levels_mpa
  })

  const damageLevels = computed(() => {
    if (!summary.value) return []
    return summary.value.dataset.damage_levels
  })

  const experimentStatsByDamage = computed(() => {
    if (!summary.value) return []
    return summary.value.experiment_stats.by_damage
  })

  const experimentStatsByStress = computed(() => {
    if (!summary.value) return []
    return summary.value.experiment_stats.by_stress
  })

  const filteredExperiments = computed(() => {
    if (!experiments.value.length) return []
    return experiments.value.filter(e =>
      e.stress_mpa === selectedStress.value && e.source_type === 'original'
    )
  })

  const stressFileMetrics = computed(() => {
    if (!byFileMetrics.value.length || !summary.value) return []
    const modelMap = { v1: 'advancedV1_multiscale_extratrees', v2: 'advancedV2_cnn_bilstm', v3: 'advancedV3_physics_fusion' }
    const modelName = modelMap[selectedModel.value]
    return byFileMetrics.value.filter(m => m.model === modelName)
  })

  const currentStressAccuracy = computed(() => {
    const files = stressFileMetrics.value
    if (!files.length) return null
    const stressMPa = selectedStress.value
    const matching = files.filter(f => f.source_file.includes(`S${String(stressMPa).padStart(2, '0')}`))
    if (!matching.length) return null
    return {
      damage_acc: (matching.reduce((s, f) => s + f.damage_accuracy, 0) / matching.length * 100).toFixed(1),
      stress_acc: (matching.reduce((s, f) => s + f.stress_accuracy, 0) / matching.length * 100).toFixed(1),
      state_acc: (matching.reduce((s, f) => s + f.state_head_accuracy, 0) / matching.length * 100).toFixed(1)
    }
  })

  // Find representative torque/thrust stats for selected stress
  const currentStressStats = computed(() => {
    if (!summary.value) return null
    const stats = summary.value.experiment_stats.by_stress.find(
      s => s.stress === selectedStress.value
    )
    if (!stats) return null
    // Also get damage-level breakdown
    const damageStats = summary.value.experiment_stats.by_damage
    return { stress: stats, damage: damageStats }
  })

  const currentTelemetrySeries = computed(() => {
    return activeBorehole.value?.samples || []
  })

  const sourceRunId = ref(null)

  function applyAnalysisResult(result) {
    if (!result) return
    const runId = result.run_id || result.sourceRunId
    activeRun.value = runId
    sourceRunId.value = runId
    analysisResult.value = result
    isDynamic.value = true
    dynamicKpis.value = result.kpis

    // Automatically switch to V3 model to display the new inference results
    selectedModel.value = 'v3'

    // The bundled reference batch must reproduce the original Mine preview
    // exactly. Replace the three baseline objects atomically instead of
    // rebuilding them from the lossy chart series returned by inference.
    if (result.referencePreview && result.ringCloud && result.spatialRoadway) {
      if (result.dashboardSummary) summary.value = result.dashboardSummary
      ringCloud.value = result.ringCloud
      spatialRoadway.value = result.spatialRoadway
      previewSource.value = 'backend-reference-run'
      if (!ringCloud.value.boreholes?.some(item => item.id === selectedBoreholeId.value)) {
        selectedBoreholeId.value = ringCloud.value.boreholes?.[0]?.id || null
      }
      return
    }

    // 1. Update V3 model accuracy in ringCloud.meta.models, isolate V1/V2 (P0-3)
    if (ringCloud.value?.meta?.models) {
      ringCloud.value.meta.models.forEach(m => {
        if (m.id === 'v3') {
          m.damageAccuracy = result.model.damage_accuracy
          m.stressAccuracy = result.model.stress_accuracy
          m.macroF1 = result.model.macro_f1
          m.confidence = result.model.confidence
          m.isCurrentRun = true
          m.hasGroundTruth = result.model.has_ground_truth
        } else {
          m.isCurrentRun = false
        }
      })
    }

    // 2. Update summary.models if present, isolate V1/V2 (P0-3)
    if (summary.value?.models) {
      summary.value.models.forEach(m => {
        if (m.id === 'v3') {
          m.damage_accuracy = result.model.damage_accuracy
          m.stress_accuracy = result.model.stress_accuracy
          m.macro_f1 = result.model.macro_f1
          m.confidence = result.model.confidence
          m.isCurrentRun = true
          m.has_ground_truth = result.model.has_ground_truth
        } else {
          m.isCurrentRun = false
        }
      })
    }

    // 3. Atomically replace 3D spatial roadway (P0-2)
    if (result.spatialRoadway) {
      spatialRoadway.value = result.spatialRoadway
      if (result.spatialRoadway.meta?.activeBoreholeId) {
        selectedBoreholeId.value = result.spatialRoadway.meta.activeBoreholeId
      }
    }

    // 4. Update ringCloud boreholes with newly inferred time-series points (P0-3: Only update v3)
    if (result.files && Array.isArray(result.files) && ringCloud.value?.boreholes) {
      result.files.forEach(f => {
        const targetHole = ringCloud.value.boreholes.find(h =>
          h.id === f.borehole_id ||
          (h.sourceFile && f.file_name && h.sourceFile.toLowerCase() === f.file_name.toLowerCase()) ||
          h.surfaceIndex === f.surfaceIndex
        )
        if (targetHole && f.series && f.series.length > 0) {
          targetHole.samples = f.series.map((item, idx) => ({
            depth: item.depth,
            sample: item.sample ?? idx,
            torque: item.torque,
            thrust: item.thrust,
            actualDamage: item.true_damage ?? null,
            actualStress: item.true_stress ?? null,
            actualState: item.state,
            predictions: {
              v1: { damage: null, stress: null, confidence: null, state: '历史基准对比 (本次未运行)', notRun: true },
              v2: { damage: null, stress: null, confidence: null, state: '历史消融基准 (本次未运行)', notRun: true },
              v3: { damage: item.damage, stress: item.stress, confidence: item.confidence, state: item.state, outlier: false }
            }
          }))
          targetHole.isCurrentRun = true
          targetHole.runId = runId
          targetHole.metrics = f.metrics
        }
      })
    } else if (result.series && result.series.length > 0 && activeBorehole.value) {
      // Single borehole fallback
      activeBorehole.value.samples = result.series.map((item, idx) => ({
        depth: item.depth,
        sample: item.sample ?? idx,
        torque: item.torque,
        thrust: item.thrust,
        actualDamage: item.true_damage ?? null,
        actualStress: item.true_stress ?? null,
        actualState: item.state,
        predictions: {
          v1: { damage: null, stress: null, confidence: null, state: '历史基准对比 (本次未运行)', notRun: true },
          v2: { damage: null, stress: null, confidence: null, state: '历史消融基准 (本次未运行)', notRun: true },
          v3: { damage: item.damage, stress: item.stress, confidence: item.confidence, state: item.state, outlier: false }
        }
      }))
      activeBorehole.value.isCurrentRun = true
      activeBorehole.value.runId = runId
    }
  }

  async function resetToStaticData() {
    activeRun.value = null
    sourceRunId.value = null
    isDynamic.value = false
    analysisResult.value = null
    dynamicKpis.value = null
    summary.value = null
    ringCloud.value = null
    spatialRoadway.value = null
    previewSource.value = null
    loaded.value = false
    await loadAll()
  }

  return {
    summary, experiments, overallMetrics, byFileMetrics, telemetry, ringCloud, spatialRoadway,
    loaded, loading, error, previewSource,
    activeRun, sourceRunId, isDynamic, analysisResult, dynamicKpis,
    selectedStress, selectedModel, selectedBoreholeId, selectedExperimentId,
    loadSummary, loadExperimentManifest, loadMetrics, loadTelemetry, loadRingCloud, loadSpatialRoadway, loadAll,
    applyAnalysisResult, resetToStaticData,
    activeModel, models, boreholes, activeBorehole, stressLevels, damageLevels,
    experimentStatsByDamage, experimentStatsByStress,
    filteredExperiments, stressFileMetrics, currentStressAccuracy,
    currentStressStats, currentTelemetrySeries
  }
})
