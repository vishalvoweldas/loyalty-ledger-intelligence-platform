"""Evaluation module computing Precision, Recall, and F1 against isolated Ground Truth."""
from sqlalchemy.orm import Session
from typing import Dict, Any, List
from loyalty_ledger.domain.models import GroundTruthRecord

class AnomalyEvaluator:
    def __init__(self, session: Session):
        self.session = session

    def evaluate(self, detected_findings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compares detector findings with GroundTruthRecord table and computes evaluation metrics.
        """
        ground_truth = self.session.query(GroundTruthRecord).all()

        gt_by_type = {}
        for gt in ground_truth:
            gt_by_type.setdefault(gt.issue_type, []).append(gt)

        detected_by_type = {}
        for d in detected_findings:
            detected_by_type.setdefault(d["issue_type"], []).append(d)

        all_types = sorted(list(set(list(gt_by_type.keys()) + list(detected_by_type.keys()))))
        class_metrics = {}

        total_tp = 0
        total_fp = 0
        total_fn = 0

        for itype in all_types:
            gts = gt_by_type.get(itype, [])
            dets = detected_by_type.get(itype, [])

            gt_records = {gt.affected_record_id for gt in gts}
            det_records = {d["affected_record_id"] for d in dets}

            tp = len(gt_records.intersection(det_records))
            fp = len(det_records - gt_records)
            fn = len(gt_records - det_records)

            precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            total_tp += tp
            total_fp += fp
            total_fn += fn

            class_metrics[itype] = {
                "ground_truth_count": len(gts),
                "detected_count": len(dets),
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1_score": round(f1, 4)
            }

        overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 1.0
        overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 1.0
        overall_f1 = (
            2 * (overall_precision * overall_recall) / (overall_precision + overall_recall)
            if (overall_precision + overall_recall) > 0 else 0.0
        )

        return {
            "overall": {
                "ground_truth_total": len(ground_truth),
                "detected_total": len(detected_findings),
                "true_positives": total_tp,
                "false_positives": total_fp,
                "false_negatives": total_fn,
                "precision": round(overall_precision, 4),
                "recall": round(overall_recall, 4),
                "f1_score": round(overall_f1, 4)
            },
            "by_class": class_metrics
        }
