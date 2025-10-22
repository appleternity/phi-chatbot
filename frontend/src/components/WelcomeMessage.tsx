export default function WelcomeMessage() {
  return (
    <div className="bg-white border-2 border-gray-200 rounded-2xl p-6 mb-6 shadow-sm">
      <h2 className="text-2xl font-bold text-primary-600 mb-4 flex items-center gap-2">
        <span>👋</span> Welcome!
      </h2>
      <p className="text-gray-700 mb-4">I'm here to help you with:</p>
      <ul className="space-y-3 mb-6">
        <li className="flex items-start gap-3">
          <span className="text-2xl">💬</span>
          <div>
            <strong className="text-gray-900">Emotional Support</strong>
            <p className="text-sm text-gray-600">If you need someone to talk to about your feelings</p>
          </div>
        </li>
        <li className="flex items-start gap-3">
          <span className="text-2xl">💊</span>
          <div>
            <strong className="text-gray-900">Medication Information</strong>
            <p className="text-sm text-gray-600">Learn about mental health medications like SSRIs, SNRIs, and more</p>
          </div>
        </li>
      </ul>
      <div className="pt-4 border-t border-gray-200">
        <p className="text-xs text-gray-500 flex items-start gap-2">
          <span>⚕️</span>
          <span>
            <strong>Disclaimer:</strong> This is an AI assistant providing information only. For medical advice, diagnosis, or treatment, please consult a qualified healthcare professional.
          </span>
        </p>
      </div>
    </div>
  )
}
