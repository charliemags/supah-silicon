#!/usr/bin/env ruby
# Benchmarks the actual Muni implementation against bounded public-data replays.
require 'optparse'
require 'digest'
require 'fileutils'
require 'tmpdir'
require 'time'
require 'rbconfig'
require 'open3'

module SupahProfile
  module_function

  def percentile(values, fraction)
    sorted = values.sort
    index = fraction * (sorted.length - 1)
    low, high = index.floor, index.ceil
    sorted[low] + (sorted[high] - sorted[low]) * (index - low)
  end

  def summarize(samples)
    raise ArgumentError, 'No measured samples' if samples.empty?
    %w[wall_s cpu_s allocated_objects gc_s].to_h do |key|
      values = samples.map { |s| s.fetch(key) }
      [key, { 'median' => percentile(values, 0.5), 'p95' => percentile(values, 0.95),
              'min' => values.min, 'max' => values.max }]
    end
  end

  def measure(name, repeats:, warmups:, units:, setup: nil, &work)
    raise ArgumentError, 'positive repetitions and units required' unless repeats.positive? && units.positive? && warmups >= 0
    samples = []
    result = nil
    (warmups + repeats).times do |i|
      setup&.call
      GC.start
      before = GC.stat
      wall = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      cpu = Process.clock_gettime(Process::CLOCK_PROCESS_CPUTIME_ID)
      result = work.call
      elapsed_cpu = Process.clock_gettime(Process::CLOCK_PROCESS_CPUTIME_ID) - cpu
      elapsed_wall = Process.clock_gettime(Process::CLOCK_MONOTONIC) - wall
      after = GC.stat
      next if i < warmups
      samples << { 'wall_s' => elapsed_wall, 'cpu_s' => elapsed_cpu,
                   'allocated_objects' => after[:total_allocated_objects] - before[:total_allocated_objects],
                   'gc_s' => (after[:time] - before[:time]) / 1000.0 }
    end
    summary = summarize(samples)
    [{ 'name' => name, 'units_per_iteration' => units, 'samples' => samples, 'summary' => summary,
       'units_per_second_median' => units / summary['wall_s']['median'],
       'cpu_to_wall_ratio' => summary['cpu_s']['median'] / summary['wall_s']['median'],
       'memory_traffic_bytes' => nil, 'energy_j' => nil }, result]
  end

  def sha(path) = Digest::SHA256.file(path).hexdigest

  def git(root, *args)
    text, status = Open3.capture2('git', '-C', root, *args)
    status.success? ? text.strip : nil
  end

  def load_corpus(cache)
    manifest = JSON.parse(File.read(File.join(cache, 'manifest.json')))
    datasets = manifest.fetch('datasets').to_h do |name, item|
      raise ArgumentError, 'Invalid corpus filename' unless %w[service_requests.json building_permits.json city_news.json city_calendar.json].include?(item['file'])
      path = File.join(cache, item.fetch('file'))
      raise ArgumentError, "Corpus hash mismatch: #{name}" unless sha(path) == item.fetch('sha256')
      rows = JSON.parse(File.read(path))
      raise ArgumentError, "Empty or mismatched corpus: #{name}" unless rows.is_a?(Array) && !rows.empty? && rows.length == item.fetch('rows')
      [name, rows]
    end
    raise ArgumentError, 'Expected all four datasets' unless datasets.keys.sort == %w[building_permits city_calendar city_news service_requests]
    [manifest, datasets]
  end

  def fetch_corpus(cache, rows)
    raise ArgumentError, 'Refusing to overwrite an existing corpus' if File.exist?(File.join(cache, 'manifest.json'))
    FileUtils.mkdir_p(cache)
    client = Muni::Clients::Socrata.new(base_url: Cambridge::SharedSoda::BASE_URL)
    definitions = {
      'service_requests' => [Cambridge::ServiceRequests::RESOURCE, 'ticket_last_updated_date_time DESC, ticket_id DESC'],
      'building_permits' => [Cambridge::BuildingPermits::RESOURCE, 'issue_date DESC, id DESC']
    }
    datasets = {}
    definitions.each do |name, (resource, order)|
      wall = Process.clock_gettime(Process::CLOCK_MONOTONIC)
      records = client.query(resource: resource, order: order, limit: rows)
      raise "No public records returned for #{name}" if records.empty?
      path = File.join(cache, "#{name}.json")
      File.write(path, JSON.generate(records))
      datasets[name] = { 'file' => File.basename(path), 'sha256' => sha(path), 'rows' => records.length,
                         'serialized_bytes' => File.size(path),
                         'url' => "#{Cambridge::SharedSoda::BASE_URL}/resource/#{resource}.json",
                         'query' => { 'order' => order, 'limit' => rows },
                         'fetch_decode_wall_s' => Process.clock_gettime(Process::CLOCK_MONOTONIC) - wall }
      warn "Fetched #{name}: #{records.length} rows"
    end
    wall = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    records = Cambridge::CityNews.new.pull(limit: 25).map(&:to_h)
    raise 'No public city news records returned' if records.empty?
    path = File.join(cache, 'city_news.json')
    File.write(path, JSON.generate(records))
    datasets['city_news'] = { 'file' => File.basename(path), 'sha256' => sha(path), 'rows' => records.length,
                              'serialized_bytes' => File.size(path), 'url' => 'https://www.cambridgema.gov/news',
                              'normalization' => 'CityNews.pull; cached normalized records',
                              'fetch_decode_wall_s' => Process.clock_gettime(Process::CLOCK_MONOTONIC) - wall }
    wall = Process.clock_gettime(Process::CLOCK_MONOTONIC)
    records = Cambridge::CityCalendar.new.pull(limit: 60).map(&:to_h)
    raise 'No public calendar records returned' if records.empty?
    path = File.join(cache, 'city_calendar.json')
    File.write(path, JSON.generate(records))
    datasets['city_calendar'] = { 'file' => File.basename(path), 'sha256' => sha(path), 'rows' => records.length,
                                  'serialized_bytes' => File.size(path), 'url' => 'https://www.cambridgema.gov/citycalendar.ics',
                                  'normalization' => 'CityCalendar.pull; cached normalized records',
                                  'fetch_decode_wall_s' => Process.clock_gettime(Process::CLOCK_MONOTONIC) - wall }
    manifest = { 'captured_at' => Time.now.utc.iso8601, 'scope' => 'Bounded Cambridge public-source sample, not a production database snapshot',
                 'datasets' => datasets }
    File.write(File.join(cache, 'manifest.json'), JSON.pretty_generate(manifest) + "\n")
  end

  def main(argv)
    opts = { rows: 5_000, repeats: 7, warmups: 2, fetch: false, query_loops: 100, prediction_loops: 1000 }
    parser = OptionParser.new do |o|
      o.banner = 'ruby profiling/muni_workloads.rb --muni-root PATH --cache PATH --output PATH [--fetch]'
      o.on('--muni-root PATH') { |v| opts[:root] = File.expand_path(v) }
      o.on('--cache PATH') { |v| opts[:cache] = File.expand_path(v) }
      o.on('--output PATH') { |v| opts[:output] = File.expand_path(v) }
      o.on('--fetch') { opts[:fetch] = true }
      o.on('--sample-rows N', Integer) { |v| opts[:sample_rows] = v }
      o.on('--rows N', Integer) { |v| opts[:rows] = v }
      o.on('--repeats N', Integer) { |v| opts[:repeats] = v }
      o.on('--warmups N', Integer) { |v| opts[:warmups] = v }
      o.on('--query-loops N', Integer) { |v| opts[:query_loops] = v }
      o.on('--prediction-loops N', Integer) { |v| opts[:prediction_loops] = v }
    end
    parser.parse!(argv)
    raise ArgumentError, parser.to_s unless %i[root cache output].all? { |k| opts[k] }
    raise ArgumentError, 'Invalid benchmark budget' unless opts[:rows].between?(10, 100_000) && opts[:repeats] >= 3 && opts[:warmups] >= 0 && opts[:query_loops].positive? && opts[:prediction_loops].positive?
    raise ArgumentError, 'sample-rows must be positive' if opts[:sample_rows] && opts[:sample_rows] < 1
    raise ArgumentError, 'Output already exists; choose a new run file' if File.exist?(opts[:output])
    ENV['BUNDLE_GEMFILE'] = File.join(opts[:root], 'Gemfile')
    require 'bundler/setup'
    require 'json'
    ENV['MUNI_ROOT'] = opts[:root]
    ENV['MUNI_LOG_LEVEL'] = 'ERROR'
    ENV['MUNI_LOG_FILE'] = File::NULL
    # No external inference is performed, even if the parent shell has credentials.
    ENV.delete('ANTHROPIC_API_KEY')
    ENV['MUNI_MAINTENANCE_ENABLED'] = '0'
    require 'muni'
    Muni.boot!(root: opts[:root])
    fetch_corpus(opts[:cache], opts[:rows]) if opts[:fetch]
    manifest, data = load_corpus(opts[:cache])
    stages = []
    record = lambda do |name, units: 1, setup: nil, &work|
      stage, result = measure(name, repeats: opts[:repeats], warmups: opts[:warmups], units: units, setup: setup, &work)
      stages << stage
      warn "#{name}: #{(stage['summary']['wall_s']['median'] * 1000).round(2)} ms per iteration"
      result
    end
    # Fetching and booting are outside measured local stages. All DB writes use a disposable DB.
    Dir.mktmpdir('supah-muni-profile-') do |scratch|
      ENV['MUNI_DB_PATH'] = File.join(scratch, 'profile.sqlite3')
      Muni::Store.reset!
      Muni::Store.ensure_tables!
      now = Time.iso8601(manifest.fetch('captured_at'))
      records = {}
      schemas = {
        'service_requests' => [Cambridge::ServiceRequests.new, :normalize_socrata],
        'building_permits' => [Cambridge::BuildingPermits.new, :normalize]
      }
      schemas.each do |name, (source, normalizer)|
        selected = opts[:sample_rows] ? data[name].first(opts[:sample_rows]) : data[name]
        payload = JSON.generate(selected)
        parsed = record.call("#{name}.json_decode", units: selected.length) { JSON.parse(payload) }
        records[name] = record.call("#{name}.normalize", units: parsed.length) { parsed.map { |row| source.send(normalizer, row) } }
        klass = records[name].first.class
        raise "Missing/duplicate normalized IDs for #{name}" unless records[name].all? { |r| !r.external_id.to_s.empty? } && records[name].map(&:external_id).uniq.length == records[name].length
        clear = -> { Muni::Store.db[klass.table_name.to_sym].delete }
        record.call("#{name}.insert_individual", units: records[name].length, setup: clear) { records[name].each { |r| Muni::Store.upsert(r) } }
        record.call("#{name}.insert_bulk", units: records[name].length, setup: clear) { Muni::Store.bulk_upsert(records[name]) }
        record.call("#{name}.update_bulk", units: records[name].length) { Muni::Store.bulk_upsert(records[name]) }
        raise 'Persistence count mismatch' unless Muni::Store.count(klass, hall: 'cambridge') == records[name].length
      end
      news = (data['city_news'] + data['city_calendar']).map { |row| Muni::Records::DigestItem.new(**row.transform_keys(&:to_sym)) }
      Muni::Store.bulk_upsert(news)
      total_records = records.values.sum(&:length) + news.length
      snapshot_bytes = Dir.glob("#{Muni::Config.db_path}*").sum { |path| File.size(path) }
      query_rows = nil
      record.call('records.indexed_query', units: opts[:query_loops]) do
        opts[:query_loops].times do
          query_rows = Muni::Data.records_for_type('service_requests', hall: 'cambridge', limit: 100)
          raise 'Query returned an empty sample' if query_rows.empty?
        end
      end
      result_json = record.call('records.json_encode', units: query_rows.length) { JSON.generate(query_rows) }
      models = {}
      models['service_requests'] = record.call('analytics.service_request_train', units: records['service_requests'].length) do
        Muni::Analytics::ServiceRequestResolution.train(hall: 'cambridge', now: now)
      end
      models['building_permits'] = record.call('analytics.permit_train', units: records['building_permits'].length) do
        Muni::Analytics::PermitProcessing.train(hall: 'cambridge', now: now)
      end
      raise 'Local prediction models are not ready on this sample' unless models.values.all? { |m| m['status'] == 'ready' }
      [{ name: 'service_requests', kind: Muni::Analytics::SERVICE_REQUEST_MODEL },
       { name: 'building_permits', kind: Muni::Analytics::PERMIT_MODEL }].each do |entry|
        Muni::Store.upsert_analytics_result(hall: 'cambridge', kind: entry[:kind], key: 'default', payload: models[entry[:name]], generated_at: now)
      end
      prediction_ready = 0
      record.call('inference.empirical_311', units: opts[:prediction_loops]) do
        prediction_ready = 0
        opts[:prediction_loops].times do |i|
          value = Muni::Analytics.predict_service_request(hall: 'cambridge', attrs: records['service_requests'][i % records['service_requests'].length].to_h)
          prediction_ready += 1 if value[:status] == 'ready'
        end
        raise 'Unready local inference result' unless prediction_ready == opts[:prediction_loops]
      end
      context = record.call('digest.context_and_rank') { Muni::Analytics::CivicDigest.source_payload(hall: 'cambridge', now: now) }
      cards = record.call('digest.select_cards') { Muni::Analytics::CivicDigest.send(:deterministic_cards, context) }
      raise 'Empty digest context' if cards.empty?
      inference_body = record.call('inference.request_prepare') do
        payload = Muni::Analytics::CivicDigest.send(:authoring_context, context, cards)
        client = Muni::AnthropicClient.new(api_key: nil)
        JSON.generate(client.send(:payload, messages: [{ role: 'user', content: JSON.generate(payload) }],
                                  system: Muni::Analytics::CivicDigest.send(:system_prompt, 'cambridge'), max_tokens: 1500, tools: nil))
      end
      plans = Muni::Store.db.fetch('EXPLAIN QUERY PLAN SELECT * FROM service_requests WHERE hall = ? ORDER BY opened_at DESC LIMIT 100', 'cambridge').all.map { |r| r[:detail] }
      report = {
        'schema_version' => 1, 'profiler_sha256' => sha(__FILE__), 'run_at' => Time.now.utc.iso8601,
        'measurement_kind' => 'Native Muni code on a bounded public-source replay; single process, warm OS caches',
        'muni' => { 'commit' => git(opts[:root], 'rev-parse', 'HEAD'),
                    'working_tree_dirty' => !git(opts[:root], 'status', '--porcelain').to_s.empty?,
                    'loaded_source_sha256' => $LOADED_FEATURES.select { |f| f.start_with?(opts[:root] + '/') && File.file?(f) }.sort.to_h { |f| [f.delete_prefix(opts[:root] + '/'), sha(f)] },
                    'gemfile_lock_sha256' => sha(File.join(opts[:root], 'Gemfile.lock')) },
        'host' => { 'ruby' => RUBY_DESCRIPTION, 'os' => RbConfig::CONFIG['host_os'], 'arch' => RbConfig::CONFIG['host_cpu'],
                    'cpu_model' => (RbConfig::CONFIG['host_os'].include?('darwin') ? Open3.capture2('sysctl', '-n', 'machdep.cpu.brand_string')[0].strip : nil) },
        'protocol' => { 'warmups' => opts[:warmups], 'repeats' => opts[:repeats],
                        'gc' => 'GC.start before each iteration; natural GC within the timed work is included',
                        'tail_latency_warning' => 'p95 is an interpolation over this small sample, not a production tail-latency guarantee',
                        'query_loops_per_iteration' => opts[:query_loops], 'prediction_loops_per_iteration' => opts[:prediction_loops],
                        'raw_data_published' => false },
        'corpus' => manifest, 'stages' => stages,
        'observations' => { 'normalized_record_count' => total_records, 'sample_rows_per_table' => records.transform_values(&:length),
                             'sample_input_sha256' => records.keys.to_h { |name| [name, Digest::SHA256.hexdigest(JSON.generate(opts[:sample_rows] ? data[name].first(opts[:sample_rows]) : data[name]))] }, 'database_and_wal_bytes_before_queries' => snapshot_bytes,
                             'query_result_rows' => query_rows.length, 'query_result_json_bytes' => result_json.bytesize,
                             'query_plan' => plans, 'model_training_samples' => models.transform_values { |m| m['sample_size'] },
                             'empirical_predictions_ready' => prediction_ready, 'digest_candidates' => context['ranked_candidates'].length,
                             'digest_cards' => cards.length, 'inference_request_json_bytes' => inference_body.bytesize,
                             'digest_coverage_warning' => 'Only news and calendar sources are loaded; no claim of a complete municipal digest' },
        'unmeasured' => { 'llm_execution' => 'Skipped by user; request preparation is not model inference',
                          'llm_input_tokens' => nil, 'llm_output_tokens' => nil, 'llm_tokens_per_second' => nil,
                          'dram_traffic_bytes' => nil, 'hardware_counters' => nil, 'wall_energy_j' => nil,
                          'peak_working_set_bytes' => nil },
        'limitations' => ['Single-host microbenchmark; no concurrency, cold-cache or full-city scale guarantee',
                          'Serialized JSON bytes are payload size, not measured DRAM traffic',
                          'Local empirical bucket prediction is separate from generative model inference',
                          'Fresh inserts and same-value updates are separate workloads; bulk batching is an existing Muni API',
                          'No claim of inference energy, custom-chip speedup, power, area or thermal behavior follows from these timings']
      }
      FileUtils.mkdir_p(File.dirname(opts[:output]))
      File.write(opts[:output], JSON.pretty_generate(report) + "\n")
      warn "Saved aggregate profile: #{opts[:output]}"
    ensure
      Muni::Store.reset!
    end
  end
end

SupahProfile.main(ARGV) if $PROGRAM_NAME == __FILE__
