"use client";

import React, { useState } from "react";

interface ChangedValueHighlightProps {
  value: any;
  isChanged: boolean;
  oldValue?: any;
}

export function ChangedValueHighlight({
  value,
  isChanged,
  oldValue,
}: ChangedValueHighlightProps) {
  const [showTooltip, setShowTooltip] = useState(false);

  // Format value for display
  const formatValue = (val: any): string => {
    if (val === null || val === undefined) {
      return "(empty)";
    }
    if (typeof val === "boolean") {
      return val ? "true" : "false";
    }
    if (typeof val === "number") {
      return val.toString();
    }
    if (typeof val === "object") {
      return JSON.stringify(val);
    }
    return String(val);
  };

  // Determine change type
  const getChangeType = (): "added" | "modified" | "removed" | null => {
    if (!isChanged) return null;

    const oldIsEmpty = oldValue === null || oldValue === undefined;
    const newIsEmpty = value === null || value === undefined;

    if (oldIsEmpty && !newIsEmpty) {
      return "added";
    }
    if (!oldIsEmpty && newIsEmpty) {
      return "removed";
    }
    return "modified";
  };

  const changeType = getChangeType();

  // Get highlight color based on change type
  const getHighlightClass = (): string => {
    if (!isChanged) return "";

    switch (changeType) {
      case "added":
        return "bg-green-100 text-green-900";
      case "removed":
        return "bg-red-100 text-red-900";
      case "modified":
        return "bg-yellow-100 text-yellow-900";
      default:
        return "bg-yellow-100";
    }
  };

  // Get change type label for tooltip
  const getChangeLabel = (): string => {
    switch (changeType) {
      case "added":
        return "Added";
      case "removed":
        return "Removed";
      case "modified":
        return "Modified";
      default:
        return "Changed";
    }
  };

  if (!isChanged) {
    return <span className="text-foreground">{formatValue(value)}</span>;
  }

  return (
    <div className="relative inline-block">
      <span
        className={`inline-block px-2 py-1 rounded font-medium cursor-help transition-all ${getHighlightClass()}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {formatValue(value)}
      </span>

      {/* Tooltip */}
      {showTooltip && (
        <div className="absolute z-50 bottom-full left-1/2 transform -translate-x-1/2 mb-3 pointer-events-none">
          <div className="bg-gray-900 text-white text-xs rounded-md py-2 px-3 whitespace-nowrap shadow-lg">
            {/* Change type label */}
            <div className="text-gray-300 text-xs uppercase tracking-wide mb-1">
              {getChangeLabel()}
            </div>

            {/* Before/After values */}
            <div className="flex items-center gap-2">
              <span className="text-gray-400">{formatValue(oldValue)}</span>
              <svg
                className="w-3 h-3 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
              <span className="text-white font-semibold">{formatValue(value)}</span>
            </div>

            {/* Arrow pointing down */}
            <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-1">
              <div className="border-4 border-transparent border-t-gray-900"></div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
