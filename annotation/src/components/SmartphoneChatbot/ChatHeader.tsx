import React from 'react';

interface ChatHeaderProps {
  displayName: string;
  avatar?: string;
  status?: string;
}

export const ChatHeader: React.FC<ChatHeaderProps> = ({
  displayName,
  avatar,
  status = 'online'
}) => {
  return (
    <div className="sticky top-0 bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 z-10">
      <div className="w-10 h-10 rounded-full bg-gradient-to-r from-[#667eea] to-[#764ba2] flex items-center justify-center text-white font-semibold">
        {avatar ? (
          <img src={avatar} alt={displayName} className="w-full h-full rounded-full object-cover" />
        ) : (
          displayName.charAt(0).toUpperCase()
        )}
      </div>
      <div className="flex-1">
        <h3 className="font-semibold text-gray-900">{displayName}</h3>
        <p className="text-xs text-gray-500">{status}</p>
      </div>
    </div>
  );
};
