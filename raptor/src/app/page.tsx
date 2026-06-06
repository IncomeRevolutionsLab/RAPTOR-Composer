import RaptorWorkflow from '@/components/RaptorWorkflow';
import AuthDashboard from '@/components/AuthDashboard';

export default function Home() {
  return (
    <main className="min-h-screen bg-neutral-950 text-white font-sans selection:bg-purple-500/30 overflow-hidden relative">
      {/* Massive Hero Header */}
      <div className="relative w-full h-[70vh] min-h-[600px] flex items-start pt-12 overflow-hidden border-b border-white/10 shadow-2xl">
        <div className="absolute inset-0 bg-neutral-950">
          <img 
            src="/real_velociraptor.png" 
            alt="Raptor Background" 
            className="w-full h-full object-cover object-[center_15%] opacity-90 mix-blend-lighten"
            style={{ transform: 'scaleX(-1)', filter: 'brightness(1.2) contrast(1.1)' }}
          />
          {/* Gradients updated to focus darkness at the top for text readability */}
          <div className="absolute inset-0 bg-gradient-to-b from-neutral-950 via-neutral-950/40 to-transparent" />
          <div className="absolute inset-0 bg-gradient-to-r from-neutral-950/80 via-transparent to-neutral-950/80" />
        </div>
        
        <div className="container mx-auto px-6 relative z-10 flex flex-col md:flex-row items-start justify-between gap-12">
          <div className="flex-1 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 bg-purple-500/20 border border-purple-500/50 rounded-full text-purple-300 text-[10px] font-black tracking-widest uppercase mb-2 backdrop-blur-md">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              RAPTOR CORE ENGINE ACTIVE
            </div>
            <h1 className="text-5xl md:text-7xl font-black tracking-tighter bg-gradient-to-r from-purple-400 via-blue-400 to-green-400 bg-clip-text text-transparent drop-shadow-2xl">
              RAPTOR V2.1 COMPOSER
            </h1>
            <p className="text-sm md:text-base text-gray-300 uppercase tracking-[0.3em] font-bold max-w-xl leading-relaxed">
              Data-Driven Shortform Automation Engine.
              <br/><span className="text-purple-400 text-xs mt-2 block">Intelligent • Aggressive • Highly Efficient</span>
            </p>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-6 py-12 relative z-10 space-y-12">
        {/* Auth Modal & Dashboard Panel */}
        <AuthDashboard />

        {/* Core 9-Step Workflow */}
        <RaptorWorkflow />

        {/* Future Social Push Placeholder */}
        <div className="max-w-5xl mx-auto flex items-center justify-center py-8 border-t border-white/5">
          <p className="text-[10px] text-gray-600 uppercase tracking-widest font-medium">Ready for Youtube / TikTok / Instagram API Social Push</p>
        </div>
      </div>
    </main>
  );
}
