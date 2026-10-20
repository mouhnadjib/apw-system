import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfx/pdfx.dart';

import '../core/api.dart';
import '../services.dart';
import 'widgets.dart';

bool looksLikePdf(Uint8List bytes) =>
    bytes.length > 4 && bytes[0] == 0x25 && bytes[1] == 0x50 && bytes[2] == 0x44 && bytes[3] == 0x46;

/// يعرض رد الجهاز التنفيذي (PDF أو صورة) من الذاكرة فقط دون كتابته على القرص.
class ReplyViewerScreen extends StatefulWidget {
  const ReplyViewerScreen({super.key, required this.questionId});

  final int questionId;

  @override
  State<ReplyViewerScreen> createState() => _ReplyViewerScreenState();
}

class _ReplyViewerScreenState extends State<ReplyViewerScreen> {
  Uint8List? _bytes;
  PdfControllerPinch? _pdf;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await ServicesScope.of(context).repo.questionReply(widget.questionId);
      if (!mounted) return;
      _pdf?.dispose();
      _pdf = looksLikePdf(res.bytes) ? PdfControllerPinch(document: PdfDocument.openData(res.bytes)) : null;
      setState(() => _bytes = res.bytes);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _pdf?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bytes = _bytes;
    Widget body;
    if (bytes == null) {
      body = _loading ? const LoadingView() : ErrorView(message: _error ?? 'تعذّر تحميل الرد', onRetry: _load);
    } else if (_pdf != null) {
      body = PdfViewPinch(controller: _pdf!);
    } else {
      body = InteractiveViewer(
        maxScale: 6,
        child: Center(child: Image.memory(bytes, errorBuilder: (_, __, ___) => const Text('تعذّر عرض الملف'))),
      );
    }
    return Scaffold(
      appBar: AppBar(title: const Text('رد الجهاز التنفيذي')),
      body: body,
    );
  }
}
