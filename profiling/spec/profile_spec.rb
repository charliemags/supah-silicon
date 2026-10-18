require 'json'
require_relative '../muni_workloads'

RSpec.describe SupahProfile do
  it 'excludes warmups while preserving the final result and counts real units' do
    calls = 0
    stage, result = described_class.measure('test', repeats: 3, warmups: 2, units: 7) { calls += 1 }
    expect(calls).to eq(5)
    expect(result).to eq(5)
    expect(stage['samples'].size).to eq(3)
    expect(stage['units_per_iteration']).to eq(7)
    expect(stage['energy_j']).to be_nil
    expect(stage['memory_traffic_bytes']).to be_nil
  end

  it 'runs preparation outside every timed iteration' do
    events = []
    described_class.measure('test', repeats: 3, warmups: 1, units: 1, setup: -> { events << :setup }) { events << :work }
    expect(events).to eq([:setup, :work] * 4)
  end

  it 'rejects invalid work and measurement budgets' do
    expect { described_class.measure('test', repeats: 0, warmups: 0, units: 1) {} }.to raise_error(ArgumentError)
    expect { described_class.measure('test', repeats: 3, warmups: 0, units: 0) {} }.to raise_error(ArgumentError)
    expect { described_class.summarize([]) }.to raise_error(ArgumentError)
  end

  it 'reports an interpolated percentile without treating it as an observed sample' do
    expect(described_class.percentile([1, 2, 3, 4, 5], 0.95)).to be_within(0.0001).of(4.8)
  end

  it 'refuses modified corpora before accepting them as measured inputs' do
    Dir.mktmpdir do |directory|
      file = File.join(directory, 'service_requests.json')
      File.write(file, '[{"id":1}]')
      manifest = { datasets: { service_requests: { file: 'service_requests.json', sha256: described_class.sha(file), rows: 1 } } }
      File.write(File.join(directory, 'manifest.json'), JSON.generate(manifest))
      File.write(file, '[{"id":2}]')
      expect { described_class.load_corpus(directory) }.to raise_error(ArgumentError, /hash mismatch/)
    end
  end

  it 'rejects corpus filenames that escape the cache directory' do
    Dir.mktmpdir do |directory|
      File.write(File.join(directory, 'manifest.json'), JSON.generate(datasets: { service_requests: { file: '../secret' } }))
      expect { described_class.load_corpus(directory) }.to raise_error(ArgumentError, /filename/)
    end
  end
end
