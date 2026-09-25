enum FrameStatus {
  accepted,
  retake,
  done,
  unknown,
}

enum RetakeReason {
  noFaceDetected,
  multipleFaces,
  faceTooFar,
  poorLightingOrBlur,
  offAngle,
  unknown,
}

class HeadPose {
  final double yaw;
  final double pitch;
  final int? sectorId;

  HeadPose({
    required this.yaw,
    required this.pitch,
    this.sectorId,
  });

  factory HeadPose.fromJson(Map<String, dynamic> json) {
    return HeadPose(
      yaw: (json['yaw'] as num?)?.toDouble() ?? 0.0,
      pitch: (json['pitch'] as num?)?.toDouble() ?? 0.0,
      sectorId: json['sector_id'] as int?,
    );
  }
}

class ProgressInfo {
  final int completedTicks;
  final int totalTicks;
  final int progressPct;
  final List<bool> activeTicks;

  ProgressInfo({
    required this.completedTicks,
    required this.totalTicks,
    required this.progressPct,
    required this.activeTicks,
  });

  factory ProgressInfo.fromJson(Map<String, dynamic> json) {
    return ProgressInfo(
      completedTicks: json['completed_ticks'] as int? ?? 0,
      totalTicks: json['total_ticks'] as int? ?? 60,
      progressPct: json['progress_pct'] as int? ?? 0,
      activeTicks: (json['active_ticks'] as List<dynamic>?)
              ?.map((e) => e as bool)
              .toList() ??
          List.filled(60, false),
    );
  }
}

class FrameResult {
  final FrameStatus status;
  final String message;
  final RetakeReason? reason;
  final double? detScore;
  final double? thresholdRequired;
  final HeadPose? headPose;
  final ProgressInfo? progress;
  final String? s3Path;

  FrameResult({
    required this.status,
    required this.message,
    this.reason,
    this.detScore,
    this.thresholdRequired,
    this.headPose,
    this.progress,
    this.s3Path,
  });

  factory FrameResult.fromJson(Map<String, dynamic> json) {
    FrameStatus status = FrameStatus.unknown;
    final statusStr = json['status']?.toString().toUpperCase();
    if (statusStr == 'ACCEPTED') status = FrameStatus.accepted;
    if (statusStr == 'RETAKE') status = FrameStatus.retake;
    if (statusStr == 'DONE') status = FrameStatus.done;

    RetakeReason? reason;
    final reasonStr = json['reason']?.toString().toUpperCase();
    if (reasonStr == 'NO_FACE_DETECTED') reason = RetakeReason.noFaceDetected;
    if (reasonStr == 'MULTIPLE_FACES') reason = RetakeReason.multipleFaces;
    if (reasonStr == 'FACE_TOO_FAR') reason = RetakeReason.faceTooFar;
    if (reasonStr == 'POOR_LIGHTING_OR_BLUR') {
      reason = RetakeReason.poorLightingOrBlur;
    }
    if (reasonStr == 'OFF_ANGLE') reason = RetakeReason.offAngle;

    return FrameResult(
      status: status,
      message: json['message'] as String? ?? '',
      reason: reason,
      detScore: (json['det_score'] as num?)?.toDouble(),
      thresholdRequired: (json['threshold_required'] as num?)?.toDouble(),
      headPose: json['head_pose'] != null
          ? HeadPose.fromJson(json['head_pose'] as Map<String, dynamic>)
          : null,
      progress: json['progress'] != null
          ? ProgressInfo.fromJson(json['progress'] as Map<String, dynamic>)
          : null,
      s3Path: json['s3_path'] as String?,
    );
  }
}
