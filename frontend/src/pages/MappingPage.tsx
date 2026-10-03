import { SavedSourceMappings } from "../components/SavedSourceMappings";

export default function MappingPage() {
  return (
    <div className="px-4 py-6 md:py-8">
      <div className="max-w-6xl mx-auto space-y-5">
        <div>
          <h1 className="text-lg font-semibold text-text-primary">Mapping</h1>
          <p className="text-sm text-text-secondary mt-1">
            Match names from your files to your books. Saved matches are reused next month.
          </p>
          <p className="text-xs text-text-secondary mt-2">
            New matches are added when you confirm names during an upload.
          </p>
        </div>
        <SavedSourceMappings />
      </div>
    </div>
  );
}
